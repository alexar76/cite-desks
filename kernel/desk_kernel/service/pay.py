"""USDC-on-Base checkout for every desk, start to finish, with nobody in the loop.

The cycle a buyer walks, and where each step lives:

    POST /api/public/pay/invoices   create_invoice()  unique micro-amount quoted
    (wallet sends USDC)             —                 no desk involvement
    scheduled poll every N seconds  scan_payments()   amount -> invoice -> settle()
    settle()                        mint_grant()      desk key written on the invoice
    GET  .../invoices/{id}          invoice_view()    the browser reads the key back
    POST /api/auth/redeem           api.redeem()      key becomes a workspace + session

`confirm_invoice()` is the impatient path: a buyer who pastes their tx hash gets the key
without waiting for the next poll. Both paths converge on `settle()`, and `settle()` is
the only place a grant is minted, so a transfer can buy exactly one desk key.

This module used to refuse to quote at all outside fixture mode, because there was no
watcher and no confirm route: a paid invoice stayed `pending` forever. Refusing was the
right call then. Wiring it is the right call now.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from desk_kernel import chain
from desk_kernel.chain import USDC_DECIMALS, ChainConfig, Rpc, RpcError, Transfer, format_usdc
from desk_kernel.demo import DEMO_CHECKOUT_CLOSED, is_demo
from desk_kernel.ids import hash_desk_key, new_desk_key, new_id
from desk_kernel.service.config import DUMMY_TREASURY, current_claim, get_settings
from desk_kernel.service.models import BaseInvoice, DeskGrant
from desk_kernel.service.plans import PLANS

log = logging.getLogger(__name__)

SALT_MAX = 10_000
# Base stamps blocks in whole seconds and the app's clock is its own, so the "older than
# the invoice" guard needs slack. It is there to reject a transfer from hours ago, never
# to argue about a fraction of a second.
CLOCK_SLACK = timedelta(minutes=2)


class GrantError(ValueError):
    pass


class PayUnavailable(RuntimeError):
    """The desk cannot honour a payment right now — quote nothing rather than take money."""


# --------------------------------------------------------------------------- rail state


def fixture_allowed(settings=None) -> bool:
    settings = settings or get_settings()
    return (settings.pay_mode or "live").lower() == "fixture" and not settings.is_production


def treasury(settings=None) -> str:
    """The address a buyer is told to pay, or "" when there is nothing safe to quote.

    In fixture mode the dummy treasury is fine — no real USDC moves. In live mode it is
    the single most dangerous value in the config: an empty PAY_BASE_ADDRESS used to fall
    back to 0x1111…, which `assert_runtime_safety` only rejects when set EXPLICITLY, so a
    buyer sent real money to an address nobody owns.
    """
    settings = settings or get_settings()
    addr = (settings.pay_base_address or "").strip().lower()
    if fixture_allowed(settings):
        return addr or DUMMY_TREASURY
    if not chain.is_address(addr) or addr == DUMMY_TREASURY:
        return ""
    return addr


def rail_enabled(settings=None) -> bool:
    settings = settings or get_settings()
    if is_demo(settings):
        return False
    if not treasury(settings):
        return False
    if fixture_allowed(settings):
        return True
    return bool(chain.rpc_url_list(settings.pay_base_rpc_url)) and chain.is_address(settings.pay_usdc_address)


def rail_closed_reason(settings=None) -> str:
    settings = settings or get_settings()
    if is_demo(settings):
        return DEMO_CHECKOUT_CLOSED
    if fixture_allowed(settings):
        return ""
    addr = (settings.pay_base_address or "").strip().lower()
    if not addr:
        return "PAY_BASE_ADDRESS is not configured; checkout is closed"
    if not chain.is_address(addr):
        return "PAY_BASE_ADDRESS is not a valid address; checkout is closed"
    if addr == DUMMY_TREASURY:
        return "PAY_BASE_ADDRESS is still the placeholder treasury; checkout is closed"
    if not chain.is_address(settings.pay_usdc_address):
        return "PAY_USDC_ADDRESS is not a valid token address; checkout is closed"
    if not chain.rpc_url_list(settings.pay_base_rpc_url):
        return "no Base RPC endpoint is reachable; checkout is closed"
    return ""


def chain_config(settings=None) -> ChainConfig:
    settings = settings or get_settings()
    pay_to = treasury(settings)
    if not pay_to:
        raise PayUnavailable(rail_closed_reason(settings) or "checkout is closed")
    return ChainConfig(
        token=settings.pay_usdc_address,
        pay_to=pay_to,
        chain_id=int(settings.pay_base_chain_id),
        confirmations=int(settings.pay_base_confirmations),
        rpc_urls=tuple(chain.rpc_url_list(settings.pay_base_rpc_url)),
        user_agent=current_claim().user_agent,
    )


_rpc_cache_lock = threading.Lock()
_rpc_cache: tuple[tuple[str, ...], chain.FailoverRpc] | None = None


def get_rpc(rpc: Rpc | None = None) -> Rpc:
    if rpc is not None:
        return rpc
    settings = get_settings()
    if fixture_allowed(settings):
        from desk_kernel.service.payfixture import get_fixture_rpc

        return get_fixture_rpc()
    cfg = chain_config(settings)
    global _rpc_cache
    with _rpc_cache_lock:
        if _rpc_cache is None or _rpc_cache[0] != cfg.rpc_urls:
            _rpc_cache = (cfg.rpc_urls, chain.FailoverRpc(cfg.rpc_urls, user_agent=cfg.user_agent))
        return _rpc_cache[1]


# ------------------------------------------------------------------------------- grants


def mint_grant(db: Session, *, plan: str, days: int, payment_ref: str) -> tuple[DeskGrant, str]:
    if plan not in PLANS:
        raise GrantError("unknown plan")
    existing = db.query(DeskGrant).filter(DeskGrant.payment_ref == payment_ref).one_or_none()
    if existing:
        raise GrantError("payment_ref already minted")
    claim = current_claim()
    key = new_desk_key(claim.key_prefix)
    now = datetime.now(timezone.utc)
    grant = DeskGrant(
        id=new_id("dsk"),
        key_hash=hash_desk_key(key),
        payment_ref=payment_ref,
        plan=plan,
        days=days,
        created_at=now,
        # The paid window is `days`; the key itself stays redeemable a fortnight longer so
        # a buyer who pays on a Friday and reads their mail on Monday is not a support case.
        expires_at=now + timedelta(days=days + 14),
    )
    db.add(grant)
    db.flush()
    return grant, key


# ------------------------------------------------------------------------------ invoices


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def grace_seconds(settings=None) -> int:
    settings = settings or get_settings()
    return max(0, int(getattr(settings, "pay_late_grace_hours", 0))) * 3600


def claim_deadline(invoice: BaseInvoice, settings=None) -> datetime:
    """Last moment a transfer can still buy this invoice.

    The quote lapses at `expires_at` — the amount is no longer offered — but a payment
    already on its way is still honoured until this deadline. Dropping it would turn a
    slow wallet into a manual refund, which is a human in the loop.
    """
    return _aware(invoice.expires_at) + timedelta(seconds=grace_seconds(settings))


def _claimable_clause(now: datetime, settings=None):
    floor = now - timedelta(seconds=grace_seconds(settings))
    return or_(
        and_(BaseInvoice.status == "pending", BaseInvoice.expires_at > now),
        and_(BaseInvoice.status == "expired", BaseInvoice.expires_at > floor),
    )


def expire_stale(db: Session) -> None:
    now = datetime.now(timezone.utc)
    for invoice in db.query(BaseInvoice).filter(BaseInvoice.status == "pending", BaseInvoice.expires_at < now).all():
        invoice.status = "expired"
    db.flush()


def allocate_amount(db: Session, plan: str) -> int:
    """A micro-amount no other claimable invoice is using — the whole payment reference.

    An expired invoice inside its grace can still be paid, so its amount is not free to
    hand to somebody else; that is why the window here is the grace window and not a
    hardcoded day.
    """
    base = int(PLANS[plan]["price_usd"]) * 10**USDC_DECIMALS
    now = datetime.now(timezone.utc)
    taken = {int(row.amount_raw) for row in db.query(BaseInvoice).filter(_claimable_clause(now))}
    for salt in range(1, SALT_MAX):
        raw = base + salt
        if raw not in taken:
            return raw
    raise PayUnavailable("no free USDC invoice slots")


def create_invoice(db: Session, *, plan: str, payment_method: str = "usdc_base") -> BaseInvoice:
    settings = get_settings()
    if plan not in PLANS:
        raise GrantError("unknown plan")
    if payment_method != "usdc_base":
        raise GrantError("only usdc_base is open")
    if not rail_enabled(settings):
        raise PayUnavailable(rail_closed_reason(settings) or "checkout is closed")
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


def refresh_status(db: Session, invoice: BaseInvoice) -> BaseInvoice:
    """Flip a lapsed quote to `expired` when it is read, so the view never lies."""
    if invoice.status == "pending" and _aware(invoice.expires_at) < datetime.now(timezone.utc):
        invoice.status = "expired"
        db.commit()
        db.refresh(invoice)
    return invoice


# ---------------------------------------------------------------------------- settlement


def settle(db: Session, invoice: BaseInvoice, transfer: Transfer) -> BaseInvoice:
    if invoice.status == "paid":
        return invoice
    try:
        _grant, key = mint_grant(db, plan=invoice.plan, days=invoice.days, payment_ref=invoice.id)
    except GrantError:
        # Already minted for this invoice: a concurrent poll and confirm both saw the same
        # transfer. Keep whichever key was issued instead of raising at the buyer.
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
    log.info("pay: invoice %s settled by %s", invoice.id, transfer.tx_hash)
    return invoice


def match_invoice(db: Session, transfer: Transfer) -> BaseInvoice | None:
    now = datetime.now(timezone.utc)
    if db.query(BaseInvoice).filter(BaseInvoice.tx_hash == transfer.tx_hash).one_or_none():
        return None
    # `first`, not `one_or_none`: two rows can still answer to one amount (an expired
    # invoice inside its grace plus a fresh quote). A buyer whose quote is still live
    # outranks one already in the grace window.
    return (
        db.query(BaseInvoice)
        .filter(
            BaseInvoice.amount_raw == transfer.amount_raw,
            BaseInvoice.desk_key.is_(None),
            _claimable_clause(now),
        )
        .order_by(case((BaseInvoice.status == "pending", 0), else_=1), BaseInvoice.created_at.desc())
        .first()
    )


#: Evidence that the unattended poll is alive. A scan that settles nothing logs nothing, so
#: without this a stopped scheduler and a quiet treasury look identical from the outside —
#: and the first person to notice would be a buyer whose USDC never bought anything.
#: Per process: the scheduler and this health field live in the same one.
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


def scan_payments(db: Session, rpc: Rpc | None = None) -> int:
    """Turn treasury transfers into desk keys. This is the hands-off half of checkout."""
    if not rail_enabled():
        return 0
    cfg = chain_config()
    client = get_rpc(rpc)
    expire_stale(db)
    db.commit()
    head = chain.current_block(client)
    settled_head = max(0, head - cfg.confirmations)
    start = max(0, settled_head - chain.LOOKBACK_BLOCKS)
    if settled_head < start:
        return 0
    settled = 0
    for transfer in chain.fetch_transfers(client, cfg, from_block=start, to_block=settled_head):
        invoice = match_invoice(db, transfer)
        if invoice is None:
            continue
        settle(db, invoice, transfer)
        settled += 1
    # Only after the walk finished: a half-scanned window is not a scan.
    _last_scan.update(at=datetime.now(timezone.utc), head=head)
    _last_scan["settled"] += settled
    if settled:
        log.info("pay: settled %d invoice(s) from treasury logs at head %d", settled, head)
    return settled


def confirm_invoice(db: Session, invoice: BaseInvoice, tx_hash: str, rpc: Rpc | None = None) -> BaseInvoice:
    if invoice.status == "paid":
        return invoice
    if invoice.status not in ("pending", "expired"):
        raise ValueError("invoice is not awaiting payment")
    cfg = chain_config()
    client = get_rpc(rpc)
    now = datetime.now(timezone.utc)
    refresh_status(db, invoice)
    deadline = claim_deadline(invoice)
    if deadline < now:
        raise ValueError("invoice expired")
    receipt = chain.fetch_receipt(client, tx_hash)
    if int(receipt.get("status") or "0x0", 16) != 1:
        raise ValueError("transaction failed")
    head = chain.current_block(client)
    block_number = int(receipt.get("blockNumber") or "0x0", 16)
    if head < block_number + cfg.confirmations:
        raise ValueError("not enough confirmations yet")
    hits = [row for row in chain.transfers_from_receipt(cfg, receipt) if row.amount_raw == invoice.amount_raw]
    if not hits:
        raise ValueError("transaction does not pay this invoice")
    if db.query(BaseInvoice).filter(BaseInvoice.tx_hash == hits[0].tx_hash).one_or_none():
        raise ValueError("that transfer already settled an invoice")
    # The scan only ever reads a window ending at the chain head, so an old transfer can
    # only reach an invoice through a hand-supplied hash. Bound it to the invoice's own
    # life, or the grace window becomes a way to claim somebody else's stray payment.
    paid_at = chain.block_time(client, block_number)
    if paid_at < _aware(invoice.created_at) - CLOCK_SLACK:
        raise ValueError("that transfer predates this invoice")
    if paid_at > deadline:
        raise ValueError("that transfer landed after the grace window")
    return settle(db, invoice, hits[0])


def simulate_payment(db: Session, invoice: BaseInvoice, rpc: Rpc | None = None) -> BaseInvoice:
    """Demo checkout: inject a transfer into the fixture chain, then let the scanner work.

    Deliberately NOT a shortcut to `paid` — it exercises fetch_transfers → match_invoice →
    settle, the same three steps a live payment takes.
    """
    if not fixture_allowed():
        raise PermissionError("fixture payments are disabled")
    if invoice.status == "paid":
        return invoice
    if invoice.status not in ("pending", "expired"):
        raise ValueError("invoice is not awaiting payment")
    refresh_status(db, invoice)
    if claim_deadline(invoice) < datetime.now(timezone.utc):
        raise ValueError("invoice expired")
    from desk_kernel.service.payfixture import get_fixture_rpc

    client = rpc or get_fixture_rpc()
    client.inject_usdc_transfer(
        token=get_settings().pay_usdc_address,
        pay_to=invoice.pay_to,
        amount_raw=invoice.amount_raw,
    )
    scan_payments(db, rpc=client)
    db.refresh(invoice)
    if invoice.status != "paid":
        raise RuntimeError("fixture transfer did not settle")
    return invoice


#: Historical name for the demo settlement route. Kept so the published API does not move.
settle_fixture = simulate_payment


# ----------------------------------------------------------------------------- rendering


def _visible_desk_key(invoice: BaseInvoice, db: Session | None) -> str | None:
    """Show the key until it has been redeemed, then stop showing it to anyone."""
    if invoice.status != "paid" or not invoice.desk_key:
        return None
    if db is None:
        return invoice.desk_key
    grant = db.query(DeskGrant).filter(DeskGrant.payment_ref == invoice.id).one_or_none()
    if grant and grant.redeemed_at:
        return None
    return invoice.desk_key


def invoice_view(invoice: BaseInvoice, db: Session | None = None) -> dict:
    settings = get_settings()
    claim = current_claim()
    spec = PLANS.get(invoice.plan, PLANS["solo"])
    amount_usdc = format_usdc(invoice.amount_raw)
    chain_id = int(settings.pay_base_chain_id)
    explorer = chain.explorer_base(chain_id)
    now = datetime.now(timezone.utc)
    deadline = claim_deadline(invoice, settings)
    paid_at = _aware(invoice.paid_at)
    return {
        "id": invoice.id,
        "number": f"{claim.invoice_prefix}-{invoice.id.replace('inv_', '')[:8].upper()}",
        "status": invoice.status,
        "plan": invoice.plan,
        "plan_name": spec["name"],
        "days": invoice.days,
        "payment_method": invoice.payment_method or "usdc_base",
        "amount_usd": spec["price_usd"],
        "amount_usdc": amount_usdc,
        "amount_raw": str(invoice.amount_raw),
        "pay_to": invoice.pay_to,
        "token": "USDC",
        "token_address": settings.pay_usdc_address.lower(),
        "decimals": USDC_DECIMALS,
        "chain": "base" if chain_id == 8453 else f"chain_{chain_id}",
        "chain_id": chain_id,
        "eip681": chain.eip681(token=settings.pay_usdc_address, chain_id=chain_id, to=invoice.pay_to, amount_raw=invoice.amount_raw),
        "confirmations_required": int(settings.pay_base_confirmations),
        "desk_key": _visible_desk_key(invoice, db),
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "expires_at": invoice.expires_at.isoformat() if invoice.expires_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "tx_hash": invoice.tx_hash,
        "from_address": invoice.from_address,
        "explorer_address": f"{explorer}/address/{invoice.pay_to}",
        "explorer_tx": f"{explorer}/tx/{invoice.tx_hash}" if invoice.tx_hash else None,
        "late": bool(paid_at and paid_at > _aware(invoice.expires_at)),
        "late_grace_hours": int(settings.pay_late_grace_hours),
        "claimable": invoice.status in ("pending", "expired") and deadline > now,
        "claim_deadline": deadline.isoformat(),
        "public_path": f"/pay/{invoice.id}",
        "fixture": fixture_allowed(settings),
        "line_items": [
            {
                "description": f"{claim.product_name} · {spec['name']} · {invoice.days} days",
                "qty": 1,
                "amount_usd": spec["price_usd"],
                "amount_usdc": amount_usdc,
            }
        ],
    }


def rail_public() -> dict:
    settings = get_settings()
    enabled = rail_enabled(settings)
    chain_id = int(settings.pay_base_chain_id)
    return {
        "enabled": enabled,
        "fixture": fixture_allowed(settings),
        "mode": "usdc_base",
        "chain": "base" if chain_id == 8453 else f"chain_{chain_id}",
        "chain_id": chain_id,
        "token": "USDC",
        "token_address": settings.pay_usdc_address.lower() if enabled else None,
        "decimals": USDC_DECIMALS,
        "pay_to": treasury(settings) if enabled else None,
        "confirmations": int(settings.pay_base_confirmations),
        "invoice_ttl_minutes": int(settings.pay_invoice_ttl_minutes),
        "late_grace_hours": int(settings.pay_late_grace_hours),
        "explorer": chain.explorer_base(chain_id),
        # A closed rail says why, so the UI can hide checkout instead of offering a
        # button that 503s.
        "closed_reason": "" if enabled else rail_closed_reason(settings),
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


__all__ = [
    "GrantError",
    "PayUnavailable",
    "RpcError",
    "allocate_amount",
    "chain_config",
    "claim_deadline",
    "confirm_invoice",
    "create_invoice",
    "expire_stale",
    "fixture_allowed",
    "format_usdc",
    "get_rpc",
    "invoice_view",
    "match_invoice",
    "mint_grant",
    "rail_closed_reason",
    "rail_enabled",
    "rail_public",
    "refresh_status",
    "scan_payments",
    "settle",
    "settle_fixture",
    "simulate_payment",
    "treasury",
]
