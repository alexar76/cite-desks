"""Emberline's payment rail, on the shared kernel chain layer.

The Base/USDC primitives — RPC failover, the chunked `eth_getLogs` walk and its window
narrowing, log parsing, receipts, block times — live in `desk_kernel.chain` and are shared
with the sibling desks. What stays here is the Emberline-shaped part: settings glue, the
`EL-` invoice and its PDF, and which invoice a given transfer belongs to.

This module used to carry its own copy of the chain layer. The copies drifted within a day
(the kernel's endpoint-list parser did not split on `;`, this one did), which is the whole
argument for keeping one: a chain bug fixed in one desk must not stay open in three others.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from desk_kernel import chain
from desk_kernel.chain import (
    LOG_WINDOW_BLOCKS,
    LOOKBACK_BLOCKS,
    TRANSFER_TOPIC,
    USDC_DECIMALS,
    ChainConfig,
    FailoverRpc,
    Rpc,
    RpcError,
    Transfer,
    eip681,
    explorer_base,
    format_usdc,
    normalize_address,
    parse_transfer_logs,
    rpc_url_list,
    topic_address,
)
from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from desk_kernel.demo import DEMO_CHECKOUT_CLOSED, is_demo

from .config import get_settings
from .grants import GrantError, mint_grant
from .models import BaseInvoice
from .plans import PLANS
from .security import new_id

log = logging.getLogger(__name__)

__all__ = [  # re-exported so callers and tests keep one import site for the rail
    "LOG_WINDOW_BLOCKS",
    "LOOKBACK_BLOCKS",
    "TRANSFER_TOPIC",
    "USDC_DECIMALS",
    "ChainConfig",
    "FailoverRpc",
    "Rpc",
    "RpcError",
    "Transfer",
    "eip681",
    "explorer_base",
    "format_usdc",
    "normalize_address",
    "parse_transfer_logs",
    "topic_address",
]

#: Stand-in treasury for the fixture desk. Never quoted in production: `assert_runtime_safety`
#: refuses to boot with PAY_MODE=fixture, and a live rail needs a real address.
TEST_TREASURY = "0x1111111111111111111111111111111111111111"
SALT_MAX = 10_000
# Base stamps blocks in whole seconds and the app's clock is its own, so the
# "older than the invoice" guard needs slack. It is there to reject a transfer
# from hours ago, never to argue about a fraction of a second.
CLOCK_SLACK = timedelta(minutes=2)
RPC_USER_AGENT = "emberline-desk/0.1 (+https://emberlinedesk.com)"
#: How often the unattended settlement poll runs. Lives here, not in `main.py`, so the
#: number an operator reads from /api/public/health is the number the scheduler uses.
PAY_SCAN_INTERVAL_SECONDS = 20


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def grace_seconds(settings=None) -> int:
    settings = settings or get_settings()
    return max(0, int(getattr(settings, "pay_late_grace_hours", 0))) * 3600


def claim_deadline(invoice: BaseInvoice, settings=None) -> datetime:
    """Last moment a transfer can still buy this invoice.

    The quote lapses at `expires_at` — the amount is no longer offered — but a
    payment already on its way is still honoured until this deadline. Dropping
    it would turn a slow wallet into a manual refund.
    """
    return _aware(invoice.expires_at) + timedelta(seconds=grace_seconds(settings))


def _claimable_clause(now: datetime, settings=None):
    floor = now - timedelta(seconds=grace_seconds(settings))
    return or_(
        and_(BaseInvoice.status == "pending", BaseInvoice.expires_at > now),
        and_(BaseInvoice.status == "expired", BaseInvoice.expires_at > floor),
    )


def fixture_allowed(settings=None) -> bool:
    settings = settings or get_settings()
    return (settings.pay_mode or "live").lower() == "fixture" and not settings.is_production


def treasury(settings=None) -> str:
    """The address this desk quotes, or "" when it has nothing safe to quote.

    Outside the fixture the placeholder is not an address, it is a hole: quoting it takes a
    customer's USDC to a wallet nobody owns and no scan will ever settle it. Refusing to
    quote costs a sale; quoting it costs the money and the customer.
    """
    settings = settings or get_settings()
    addr = (settings.pay_base_address or "").strip()
    demo = fixture_allowed(settings)
    if not addr and demo:
        addr = TEST_TREASURY
    if not demo and addr.lower() == TEST_TREASURY:
        return ""
    try:
        return normalize_address(addr)
    except ValueError:
        return ""


def rail_enabled(settings=None) -> bool:
    settings = settings or get_settings()
    if is_demo(settings):
        return False
    if not treasury(settings):
        return False
    if fixture_allowed(settings):
        return True
    return bool(rpc_urls(settings))


def rpc_urls(settings=None) -> list[str]:
    settings = settings or get_settings()
    return rpc_url_list(settings.pay_base_rpc_url)


def rail_closed_reason(settings=None) -> str:
    """Why this desk cannot sell, in one line an operator can act on.

    Same contract as the kernel's: a closed rail shows up on the buyer's side as a 503 and
    nowhere else, so the reason has to be readable from `/api/public/health`.
    """
    settings = settings or get_settings()
    if is_demo(settings):
        return DEMO_CHECKOUT_CLOSED
    if fixture_allowed(settings):
        return ""
    addr = (settings.pay_base_address or "").strip().lower()
    if not addr:
        return "PAY_BASE_ADDRESS is not configured; checkout is closed"
    # Before validity: the placeholder IS a well-formed address, and `treasury()` already
    # refuses it outside the fixture, so checking shape first would report the wrong cause.
    if addr == TEST_TREASURY:
        return "PAY_BASE_ADDRESS is still the placeholder treasury; checkout is closed"
    if not treasury(settings):
        return "PAY_BASE_ADDRESS is not a valid address; checkout is closed"
    if not rpc_urls(settings):
        return "no Base RPC endpoint is reachable; checkout is closed"
    return ""


def checkout_state(settings=None) -> dict[str, Any]:
    """The operator-facing answer to "can this desk take money without a human?"."""
    settings = settings or get_settings()
    open_rail = rail_enabled(settings) and not rail_closed_reason(settings)
    scheduled = bool(open_rail and settings.scheduler_enabled and settings.app_env != "test")
    return {
        "open": open_rail,
        "reason": "" if open_rail else (rail_closed_reason(settings) or "checkout is closed"),
        "settlement": "scheduled" if scheduled else "off",
        "scan_interval_seconds": PAY_SCAN_INTERVAL_SECONDS,
        # Proof, not intent: an `age_seconds` older than the interval means the poll stopped.
        "last_scan": last_scan(),
    }


#: Evidence that the unattended poll is alive. A scan that settles nothing logs nothing, so
#: without this a stopped scheduler and a quiet treasury look identical from the outside.
#: Per process: the scheduler and this field live in the same one.
_last_scan: dict[str, Any] = {"at": None, "head": 0, "settled": 0}


def last_scan() -> dict[str, Any]:
    at = _last_scan["at"]
    now = datetime.now(timezone.utc)
    return {
        "at": at.isoformat() if at else None,
        "age_seconds": round((now - at).total_seconds(), 1) if at else None,
        "chain_head": int(_last_scan["head"]) or None,
        "settled_total": int(_last_scan["settled"]),
    }


def chain_config(settings=None) -> ChainConfig:
    settings = settings or get_settings()
    return ChainConfig(
        token=settings.pay_usdc_address,
        pay_to=treasury(settings),
        chain_id=int(settings.pay_base_chain_id),
        confirmations=int(settings.pay_base_confirmations),
        rpc_urls=tuple(rpc_urls(settings)),
        user_agent=RPC_USER_AGENT,
    )


METHODS = {
    "usdc_base": {
        "id": "usdc_base",
        "label": "USDC on Base",
        "kind": "crypto",
        "token": "USDC",
        "chain": "base",
    },
    "wire": {
        "id": "wire",
        "label": "Wire / ACH",
        "kind": "fiat",
        "reason": "Not open yet",
    },
    "card": {
        "id": "card",
        "label": "Card",
        "kind": "fiat",
        "reason": "Not open yet",
    },
}


def invoice_number(invoice_id: str) -> str:
    return f"EL-{invoice_id.replace('inv_', '')[:8].upper()}"


def rail_public() -> dict[str, Any]:
    settings = get_settings()
    enabled = rail_enabled(settings)
    token = (settings.pay_usdc_address or "").lower()
    pay_to = (settings.pay_base_address or "").lower()
    if enabled and not pay_to:
        pay_to = "0x1111111111111111111111111111111111111111"
    chain_id = int(settings.pay_base_chain_id)
    return {
        "enabled": enabled,
        "fixture": fixture_allowed(settings),
        "mode": "usdc_base",
        "chain": "base" if chain_id == 8453 else f"chain_{chain_id}",
        "chain_id": chain_id,
        "token": "USDC",
        "token_address": token if enabled else None,
        "decimals": USDC_DECIMALS,
        "pay_to": pay_to if enabled else None,
        "confirmations": int(settings.pay_base_confirmations),
        "invoice_ttl_minutes": int(settings.pay_invoice_ttl_minutes),
        "late_grace_hours": int(settings.pay_late_grace_hours),
        "explorer": explorer_base(chain_id),
        "closed_reason": "" if enabled else rail_closed_reason(settings),
        "methods": [
            {
                **spec,
                "available": spec["id"] == "usdc_base" and enabled,
            }
            for spec in METHODS.values()
        ],
        "plans": {
            code: {
                "name": spec["name"],
                "price_usd": spec["price_usd"],
                "days": 30,
                "watches": spec["watches"],
                "runs": spec["runs"],
            }
            for code, spec in PLANS.items()
        },
    }


def expire_stale(db: Session) -> None:
    now = datetime.now(timezone.utc)
    for invoice in (
        db.query(BaseInvoice)
        .filter(BaseInvoice.status == "pending", BaseInvoice.expires_at < now)
        .all()
    ):
        invoice.status = "expired"
    db.flush()


def allocate_amount(db: Session, plan: str) -> int:
    base = int(PLANS[plan]["price_usd"]) * 10**USDC_DECIMALS
    now = datetime.now(timezone.utc)
    # An expired invoice inside its grace can still be paid, so its amount is
    # not free to hand to somebody else.
    taken = {
        int(row.amount_raw)
        for row in db.query(BaseInvoice).filter(_claimable_clause(now))
    }
    for salt in range(1, SALT_MAX):
        raw = base + salt
        if raw not in taken:
            return raw
    raise RuntimeError("no free USDC invoice slots")


def create_invoice(db: Session, *, plan: str, payment_method: str = "usdc_base") -> BaseInvoice:
    settings = get_settings()
    if payment_method != "usdc_base":
        raise ValueError("only usdc_base is open")
    if not rail_enabled(settings):
        raise RuntimeError("USDC Base rail is not configured")
    if plan not in PLANS:
        raise ValueError("unknown plan")
    expire_stale(db)
    now = datetime.now(timezone.utc)
    invoice = BaseInvoice(
        id=new_id("inv"),
        plan=plan,
        payment_method=payment_method,
        days=30,
        amount_raw=allocate_amount(db, plan),
        status="pending",
        pay_to=treasury(settings),
        expires_at=now + timedelta(minutes=int(settings.pay_invoice_ttl_minutes)),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def _visible_desk_key(invoice: BaseInvoice, db: Session | None) -> str | None:
    if invoice.status != "paid" or not invoice.desk_key:
        return None
    if db is None:
        return invoice.desk_key
    from .models import DeskGrant

    grant = db.query(DeskGrant).filter(DeskGrant.payment_ref == invoice.id).one_or_none()
    if grant and grant.redeemed_at:
        return None
    return invoice.desk_key


def invoice_view(invoice: BaseInvoice, db: Session | None = None) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    deadline = claim_deadline(invoice, settings)
    paid_at = _aware(invoice.paid_at)
    token = settings.pay_usdc_address.lower()
    chain_id = int(settings.pay_base_chain_id)
    explorer = explorer_base(chain_id)
    spec = PLANS.get(invoice.plan, PLANS["solo"])
    amount_usdc = format_usdc(invoice.amount_raw)
    method = invoice.payment_method or "usdc_base"
    number = invoice_number(invoice.id)
    return {
        "id": invoice.id,
        "number": number,
        "status": invoice.status,
        "plan": invoice.plan,
        "plan_name": spec["name"],
        "days": invoice.days,
        "payment_method": method,
        "payment_method_label": METHODS.get(method, {}).get("label", method),
        "line_items": [
            {
                "description": f"Emberline {spec['name']} desk · {invoice.days} days",
                "qty": 1,
                "amount_usd": spec["price_usd"],
                "amount_usdc": amount_usdc,
            }
        ],
        "amount_usd": spec["price_usd"],
        "chain_id": chain_id,
        "chain": "base" if chain_id == 8453 else f"chain_{chain_id}",
        "token": "USDC",
        "token_address": token,
        "decimals": USDC_DECIMALS,
        "pay_to": invoice.pay_to,
        "amount_usdc": amount_usdc,
        "amount_raw": str(invoice.amount_raw),
        "eip681": eip681(token=token, chain_id=chain_id, to=invoice.pay_to, amount_raw=invoice.amount_raw),
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "expires_at": invoice.expires_at.isoformat() if invoice.expires_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "tx_hash": invoice.tx_hash,
        "from_address": invoice.from_address,
        "explorer_address": f"{explorer}/address/{invoice.pay_to}",
        "explorer_tx": f"{explorer}/tx/{invoice.tx_hash}" if invoice.tx_hash else None,
        "confirmations_required": int(settings.pay_base_confirmations),
        "late": bool(paid_at and paid_at > _aware(invoice.expires_at)),
        "late_grace_hours": int(settings.pay_late_grace_hours),
        "claimable": invoice.status in ("pending", "expired") and deadline > now,
        "claim_deadline": deadline.isoformat(),
        "public_path": f"/pay/{invoice.id}",
        "desk_key": _visible_desk_key(invoice, db),
        "fixture": fixture_allowed(settings),
    }


def settle(db: Session, invoice: BaseInvoice, transfer: Transfer) -> BaseInvoice:
    if invoice.status == "paid":
        return invoice
    try:
        _grant, key = mint_grant(
            db,
            plan=invoice.plan,
            days=invoice.days,
            payment_ref=invoice.id,
        )
    except GrantError:
        if invoice.desk_key:
            return invoice
        raise
    invoice.status = "paid"
    invoice.tx_hash = transfer.tx_hash
    invoice.from_address = transfer.frm
    invoice.block_number = transfer.block_number
    invoice.paid_at = datetime.now(timezone.utc)
    invoice.desk_key = key
    db.commit()
    db.refresh(invoice)
    return invoice


_rpc_cache_lock = threading.Lock()
_rpc_cache: tuple[tuple[str, ...], FailoverRpc] | None = None


def _rpc(rpc: Rpc | None = None) -> Rpc:
    if rpc is not None:
        return rpc
    settings = get_settings()
    if fixture_allowed(settings):
        from .payfixture import get_fixture_rpc

        return get_fixture_rpc()
    urls = rpc_urls(settings)
    if not urls:
        raise RpcError("PAY_BASE_RPC_URL is not set")
    key = tuple(urls)
    global _rpc_cache
    with _rpc_cache_lock:
        if _rpc_cache is None or _rpc_cache[0] != key:
            _rpc_cache = (key, FailoverRpc(urls, user_agent=RPC_USER_AGENT))
        return _rpc_cache[1]


def simulate_payment(db: Session, invoice: BaseInvoice) -> BaseInvoice:
    if not fixture_allowed():
        raise PermissionError("fixture payments are disabled")
    if invoice.status == "paid":
        return invoice
    if invoice.status not in ("pending", "expired"):
        raise ValueError("invoice is not awaiting payment")
    expire_stale(db)
    db.commit()
    db.refresh(invoice)
    if claim_deadline(invoice) < datetime.now(timezone.utc):
        raise ValueError("invoice expired")
    settings = get_settings()
    from .payfixture import get_fixture_rpc

    rpc = get_fixture_rpc()
    rpc.inject_usdc_transfer(
        token=settings.pay_usdc_address,
        pay_to=invoice.pay_to,
        amount_raw=invoice.amount_raw,
    )
    scan_payments(db, rpc=rpc)
    db.refresh(invoice)
    if invoice.status != "paid":
        raise RuntimeError("fixture transfer did not settle")
    return invoice


# The chain calls themselves are the kernel's. These wrappers exist only to keep this
# module's "settings + optional rpc" shape, which the routers and tests already speak.
def current_block(rpc: Rpc | None = None) -> int:
    return chain.current_block(_rpc(rpc))


def fetch_transfers(*, from_block: int, to_block: int, rpc: Rpc | None = None) -> list[Transfer]:
    return chain.fetch_transfers(
        _rpc(rpc), chain_config(), from_block=from_block, to_block=to_block
    )


def fetch_receipt(tx_hash: str, rpc: Rpc | None = None) -> dict[str, Any]:
    return chain.fetch_receipt(_rpc(rpc), tx_hash)


def transfers_from_receipt(receipt: dict[str, Any]) -> list[Transfer]:
    return chain.transfers_from_receipt(chain_config(), receipt)


def match_invoice(db: Session, transfer: Transfer) -> BaseInvoice | None:
    now = datetime.now(timezone.utc)
    if db.query(BaseInvoice).filter(BaseInvoice.tx_hash == transfer.tx_hash).one_or_none():
        return None
    # `first`, not `one_or_none`: invoices written before the grace existed
    # reused amounts freely, so two rows can still answer to one transfer. A
    # buyer whose quote is still live outranks one already in the grace window.
    return (
        db.query(BaseInvoice)
        .filter(
            BaseInvoice.amount_raw == transfer.amount_raw,
            BaseInvoice.desk_key.is_(None),
            _claimable_clause(now),
        )
        .order_by(
            case((BaseInvoice.status == "pending", 0), else_=1),
            BaseInvoice.created_at.desc(),
        )
        .first()
    )


def block_time(block_number: int, rpc: Rpc | None = None) -> datetime:
    return chain.block_time(_rpc(rpc), block_number)


def confirm_invoice(db: Session, invoice: BaseInvoice, tx_hash: str, rpc: Rpc | None = None) -> BaseInvoice:
    if invoice.status == "paid":
        return invoice
    if invoice.status not in ("pending", "expired"):
        raise ValueError("invoice is not awaiting payment")
    now = datetime.now(timezone.utc)
    if invoice.status == "pending" and _aware(invoice.expires_at) < now:
        invoice.status = "expired"
        db.commit()
    deadline = claim_deadline(invoice)
    if deadline < now:
        raise ValueError("invoice expired")
    receipt = fetch_receipt(tx_hash, rpc)
    if int(receipt.get("status") or "0x0", 16) != 1:
        raise ValueError("transaction failed")
    head = current_block(rpc)
    block_number = int(receipt.get("blockNumber") or "0x0", 16)
    needed = int(get_settings().pay_base_confirmations)
    if head < block_number + needed:
        raise ValueError("not enough confirmations yet")
    hits = [row for row in transfers_from_receipt(receipt) if row.amount_raw == invoice.amount_raw]
    if not hits:
        raise ValueError("transaction does not pay this invoice")
    # The scan only ever reads a window ending at the chain head, so an old
    # transfer can only reach an invoice through a hand-supplied hash. Bound it
    # to the invoice's own life, or the grace window becomes a way to claim
    # somebody else's stray payment.
    paid_at = block_time(block_number, rpc)
    if paid_at < _aware(invoice.created_at) - CLOCK_SLACK:
        raise ValueError("that transfer predates this invoice")
    if paid_at > deadline:
        raise ValueError("that transfer landed after the grace window")
    return settle(db, invoice, hits[0])


def scan_payments(db: Session, rpc: Rpc | None = None) -> int:
    if not rail_enabled():
        return 0
    expire_stale(db)
    db.commit()
    head = current_block(rpc)
    needed = int(get_settings().pay_base_confirmations)
    settled_head = max(0, head - needed)
    start = max(0, settled_head - LOOKBACK_BLOCKS)
    if settled_head < start:
        return 0
    settled = 0
    for transfer in fetch_transfers(from_block=start, to_block=settled_head, rpc=rpc):
        invoice = match_invoice(db, transfer)
        if invoice is None:
            continue
        settle(db, invoice, transfer)
        settled += 1
    # Only after the walk finished: a half-scanned window is not a scan.
    _last_scan.update(at=datetime.now(timezone.utc), head=head)
    _last_scan["settled"] += settled
    if settled:
        log.info("basepay: settled %d invoice(s) from treasury logs at head %d", settled, head)
    return settled


def render_invoice_pdf(invoice: BaseInvoice) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    view = invoice_view(invoice)

    class BillPDF(FPDF):
        def header(self) -> None:
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(90, 70, 55)
            self.set_x(self.l_margin)
            self.multi_cell(0, 4, "EMBERLINE  |  INVOICE  |  USDC ON BASE", wrapmode="CHAR")
            self.set_draw_color(180, 150, 120)
            y = self.get_y() + 1
            self.line(16, y, 194, y)
            self.set_xy(self.l_margin, y + 4)

        def footer(self) -> None:
            self.set_y(-14)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(110, 95, 80)
            self.cell(
                0,
                8,
                "Send the exact USDC amount. A rounded transfer will not settle.\n"
                "A late transfer still settles inside the grace window on the invoice.",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="C",
            )

    pdf = BillPDF(format="A4")
    created = invoice.created_at or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    pdf.set_creation_date(created)
    pdf.set_title(view["number"])
    pdf.set_author("Emberline")
    pdf.set_creator("emberline.invoice@v1")
    pdf.set_margins(16, 18, 16)
    pdf.add_page()

    def write(text: str, *, size: int = 10, bold: bool = False, h: int = 5) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.set_text_color(26, 18, 14)
        pdf.multi_cell(0, h, str(text), wrapmode="CHAR")

    write(f"Invoice {view['number']}", size=20, bold=True, h=9)
    write(f"{view['status'].upper()}  |  {view['payment_method_label']}")
    write(f"Issued {view.get('created_at') or ''}  |  due {view.get('expires_at') or ''}")
    pdf.ln(3)
    write("Line", size=11, bold=True)
    for item in view["line_items"]:
        write(f"{item['description']}    ${item['amount_usd']}    {item['amount_usdc']} USDC")
    pdf.ln(2)
    write(f"Amount due  {view['amount_usdc']} USDC", size=14, bold=True, h=7)
    write(f"List price ${view['amount_usd']}. Unique cents identify this invoice.")
    pdf.ln(2)
    write("Pay to (Base)", size=11, bold=True)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Courier", "", 9)
    pdf.multi_cell(0, 5, view["pay_to"], wrapmode="CHAR")
    write(f"Token {view['token_address']}")
    write(f"Chain Base ({view['chain_id']})")
    if view.get("tx_hash"):
        write(f"Tx {view['tx_hash']}")
    return bytes(pdf.output())
