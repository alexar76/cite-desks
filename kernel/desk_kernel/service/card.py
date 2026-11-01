"""Card checkout for every desk, through Stripe Checkout, with nobody in the loop.

The same desk key a USDC payment buys, by a second road:

    POST /api/public/pay/card              create_card_invoice()  invoice + Checkout Session
    (buyer pays on checkout.stripe.com)    —                      the desk never sees a card
    POST /api/public/pay/stripe/webhook    handle_webhook()       checkout.session.completed
    POST .../invoices/{id}/card/refresh    refresh_card()         the buyer is back, webhook not yet
    scheduled poll                         sweep_card_invoices()  tab closed AND webhook lost
    settle_card()                          pay.mint_grant()       desk key written on the invoice

Every path converges on `settle_card()`, and every figure it checks comes from the row this
desk opened, never from the event: an event names an invoice, and a forged or replayed one
must not choose the plan or the amount. A refund or a dispute ends the access it bought.

Closed in demo mode, like the USDC rail. A test key opens only outside production and a
live key only in production, so a test card can never buy a real desk key and a
development desk can never charge a real card.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from desk_kernel.demo import DEMO_CHECKOUT_CLOSED, is_demo
from desk_kernel.ids import new_id
from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.service.models import BaseInvoice, CardCheckout, DeskGrant, Workspace
from desk_kernel.service.pay import GrantError, PayUnavailable, _aware, mint_grant
from desk_kernel.service.plans import PLANS

log = logging.getLogger(__name__)

CARD = "card_stripe"
STRIPE_API = "https://api.stripe.com"
STRIPE_VERSION = "2024-06-20"
SIGNATURE_TOLERANCE_S = 300
#: Stripe accepts a Checkout Session expiry between 30 minutes and 24 hours from now.
SESSION_MIN = timedelta(minutes=31)
SESSION_MAX = timedelta(hours=23)
PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
#: One Stripe read per open invoice per this many seconds, whoever asks.
REFRESH_EVERY_S = 5
SWEEP_EVERY_S = 60
SWEEP_BATCH = 20

StripeCall = Callable[..., tuple[int, dict[str, Any]]]


class CardRefused(ValueError):
    """Stripe's answer does not match the checkout this desk opened; nothing is granted."""


# --------------------------------------------------------------------------- rail state


def _live_key(key: str) -> bool:
    return key.startswith(("sk_live_", "rk_live_"))


def card_closed_reason(settings=None) -> str:
    settings = settings or get_settings()
    if is_demo(settings):
        return DEMO_CHECKOUT_CLOSED
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        return "STRIPE_SECRET_KEY is not configured; card checkout is closed"
    if not (settings.stripe_webhook_secret or "").strip():
        return "STRIPE_WEBHOOK_SECRET is not configured; card checkout is closed"
    if not key.startswith(("sk_live_", "rk_live_", "sk_test_", "rk_test_")):
        return "STRIPE_SECRET_KEY is not a Stripe secret or restricted key; card checkout is closed"
    if settings.is_production and not _live_key(key):
        return "a Stripe test key on a production desk would sell real desk keys for test cards; card checkout is closed"
    if not settings.is_production and _live_key(key):
        return "a Stripe live key outside production would charge real cards; card checkout is closed"
    return ""


def card_enabled(settings=None) -> bool:
    return not card_closed_reason(settings)


def card_public(settings=None) -> dict:
    settings = settings or get_settings()
    reason = card_closed_reason(settings)
    return {
        "enabled": not reason,
        "provider": "stripe-checkout",
        "currency": "usd",
        "test_mode": not reason and not _live_key(settings.stripe_secret_key.strip()),
        "closed_reason": reason,
    }


# ------------------------------------------------------------------------- Stripe over HTTP


def _form(obj: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: nested keys as ``a[b][0][c]``."""
    out: list[tuple[str, str]] = []
    for key, value in obj.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            out.extend(_form(value, name))
        elif isinstance(value, list):
            out.extend(_form({str(i): v for i, v in enumerate(value)}, name))
        elif value is not None:
            out.append((name, str(value).lower() if isinstance(value, bool) else str(value)))
    return out


def _stripe_request(method: str, path: str, *, form: dict[str, Any] | None = None,
                    idempotency_key: str = "") -> tuple[int, dict[str, Any]]:
    import httpx

    headers = {
        "Authorization": f"Bearer {get_settings().stripe_secret_key.strip()}",
        "Stripe-Version": STRIPE_VERSION,
        "User-Agent": current_claim().user_agent,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    body = None
    if form is not None:
        # Encoded here: httpx reads a list of pairs passed as `data=` as a byte stream, and
        # Stripe's nested keys need the pairs.
        body = urlencode(_form(form)).encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    with httpx.Client(timeout=20.0, follow_redirects=False) as client:
        response = client.request(method, f"{STRIPE_API}{path}", headers=headers, content=body)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def verify_signature(payload: bytes, header: str, secret: str, *, now: float | None = None,
                     tolerance_s: int = SIGNATURE_TOLERANCE_S) -> bool:
    """``Stripe-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "t.payload">`` (several v1 while a
    secret is rolled), fresh within ``tolerance_s``, compared in constant time."""
    if not secret or not header:
        return False
    stamp = ""
    signatures: list[str] = []
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            stamp = value
        elif key == "v1" and value:
            signatures.append(value)
    if not stamp.isdigit() or not signatures:
        return False
    now = time.time() if now is None else now
    if abs(now - int(stamp)) > tolerance_s:
        return False
    want = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(want, s) for s in signatures)


# ------------------------------------------------------------------------------ invoices


def price_cents(plan: str) -> int:
    return int(PLANS[plan]["price_usd"]) * 100


def create_card_invoice(db: Session, *, plan: str, stripe: StripeCall | None = None) -> BaseInvoice:
    """Open an invoice and its Checkout Session. Nothing is charged here."""
    settings = get_settings()
    if plan not in PLANS:
        raise GrantError("unknown plan")
    reason = card_closed_reason(settings)
    if reason:
        raise PayUnavailable(reason)
    stripe = stripe or _stripe_request
    claim = current_claim()
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=int(settings.pay_invoice_ttl_minutes))
    expires = now + min(max(ttl, SESSION_MIN), SESSION_MAX)
    invoice = BaseInvoice(
        id=new_id("inv"),
        plan=plan,
        payment_method=CARD,
        days=30,
        # Cents, not USDC units: the USDC matcher only reads usdc_base rows.
        amount_raw=price_cents(plan),
        status="pending",
        pay_to="stripe",
        expires_at=expires,
    )
    db.add(invoice)
    db.commit()
    back = f"{settings.public_url.rstrip('/')}/pay/{invoice.id}"
    form = {
        "mode": "payment",
        "client_reference_id": invoice.id,
        "success_url": f"{back}?card=return",
        "cancel_url": f"{back}?card=cancel",
        "expires_at": int(expires.timestamp()),
        # Cards settle synchronously; a delayed method would leave the buyer with no key and
        # no way to tell when one comes.
        "payment_method_types": ["card"],
        "metadata": {"invoice_id": invoice.id, "desk": claim.id, "plan": plan},
        "payment_intent_data": {"metadata": {"invoice_id": invoice.id, "desk": claim.id}},
        "line_items": [{"quantity": 1, "price_data": {
            "currency": "usd",
            "unit_amount": price_cents(plan),
            "product_data": {"name": f"{claim.product_name} · {PLANS[plan]['name']} · {invoice.days} days"},
        }}],
    }
    try:
        status, session = stripe("POST", "/v1/checkout/sessions", form=form, idempotency_key=invoice.id)
    except Exception as exc:  # noqa: BLE001 - Stripe unreachable
        invoice.status = "failed"
        db.commit()
        log.error("card: Stripe unreachable opening %s: %s", invoice.id, type(exc).__name__)
        raise PayUnavailable("the card processor could not be reached; nothing was charged") from None
    url = str(session.get("url") or "")
    session_id = str(session.get("id") or "")
    if status >= 300 or not url.startswith("https://") or not session_id.startswith("cs_"):
        invoice.status = "failed"
        db.commit()
        message = str((session.get("error") or {}).get("message") or f"HTTP {status}")
        log.error("card: Stripe refused a session for %s: %s", invoice.id, message)
        raise PayUnavailable("the card processor refused to open a checkout; nothing was charged")
    db.add(CardCheckout(invoice_id=invoice.id, session_id=session_id, checkout_url=url,
                        livemode=bool(session.get("livemode"))))
    db.commit()
    db.refresh(invoice)
    return invoice


# ---------------------------------------------------------------------------- settlement


def _payment_intent(session: dict[str, Any]) -> str:
    value = session.get("payment_intent")
    if isinstance(value, dict):
        value = value.get("id")
    return str(value or "")


def settle_card(db: Session, invoice: BaseInvoice, session: dict[str, Any]) -> BaseInvoice:
    """Mint the desk key for a paid session, once. Shared by the webhook, refresh and sweep."""
    if invoice.status == "paid" or invoice.payment_method != CARD:
        return invoice
    checkout = db.get(CardCheckout, invoice.id)
    if checkout is None or str(session.get("id") or "") != checkout.session_id:
        raise CardRefused("that session does not belong to this invoice")
    if checkout.status in ("refunded", "disputed"):
        raise CardRefused(f"the payment was {checkout.status}")
    if session.get("payment_status") != "paid":
        return invoice
    total = session.get("amount_total")
    if str(session.get("currency") or "").lower() != "usd" or total != invoice.amount_raw:
        checkout.note = f"paid {total} {session.get('currency')}, expected {invoice.amount_raw} usd"
        db.commit()
        log.error("card: %s paid %s %s, expected %s usd cents — NOT granted, check it in Stripe",
                  invoice.id, total, session.get("currency"), invoice.amount_raw)
        raise CardRefused("amount or currency differs from the checkout opened")
    if _live_key(get_settings().stripe_secret_key.strip()) and not session.get("livemode"):
        log.error("card: test-mode payment for %s on a live key — not granted", invoice.id)
        raise CardRefused("test-mode payment on a live desk")
    try:
        _grant, key = mint_grant(db, plan=invoice.plan, days=invoice.days, payment_ref=invoice.id)
    except (GrantError, IntegrityError):
        # The webhook and a refresh saw the same payment at once: keep the key the other
        # one wrote instead of failing at the buyer.
        db.rollback()
        db.refresh(invoice)
        if invoice.desk_key or invoice.status == "paid":
            return invoice
        raise
    invoice.status = "paid"
    invoice.paid_at = datetime.now(timezone.utc)
    invoice.desk_key = key
    checkout.status = "paid"
    checkout.payment_intent = _payment_intent(session)
    db.commit()
    db.refresh(invoice)
    log.warning("card: invoice %s settled by %s", invoice.id, checkout.session_id[:24])
    return invoice


def _expire(db: Session, invoice: BaseInvoice, checkout: CardCheckout) -> None:
    if invoice.status == "pending":
        invoice.status = "expired"
    if checkout.status == "open":
        checkout.status = "expired"
    db.commit()


def refresh_card(db: Session, invoice: BaseInvoice, *, stripe: StripeCall | None = None,
                 every_s: int = REFRESH_EVERY_S) -> BaseInvoice:
    """Read the session back from Stripe: the recovery path for a webhook that has not come."""
    if invoice.payment_method != CARD or invoice.status not in ("pending", "expired"):
        return invoice
    checkout = db.get(CardCheckout, invoice.id)
    if checkout is None or checkout.status != "open":
        return invoice
    now = datetime.now(timezone.utc)
    checked = _aware(checkout.checked_at)
    if checked is not None and now - checked < timedelta(seconds=every_s):
        return invoice
    # Not card_enabled(): a desk that closed card sales since (demo mode, say) still owes
    # the key for a session that was already open. Only a missing key stops the read.
    if not get_settings().stripe_secret_key.strip():
        raise PayUnavailable("STRIPE_SECRET_KEY is not configured")
    checkout.checked_at = now
    db.commit()
    stripe = stripe or _stripe_request
    try:
        status, session = stripe("GET", f"/v1/checkout/sessions/{checkout.session_id}")
    except Exception:  # noqa: BLE001
        raise PayUnavailable("the card processor could not be reached; retry") from None
    if status >= 300:
        raise PayUnavailable(f"the card processor answered HTTP {status}")
    if session.get("status") == "expired" and session.get("payment_status") != "paid":
        _expire(db, invoice, checkout)
        return invoice
    return settle_card(db, invoice, session)


def sweep_card_invoices(db: Session, *, stripe: StripeCall | None = None) -> int:
    """The unattended half: open card invoices whose buyer closed the tab and whose webhook
    was lost still turn into keys. Returns how many settled."""
    if not card_enabled():
        return 0
    floor = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = (
        db.query(BaseInvoice)
        .join(CardCheckout, CardCheckout.invoice_id == BaseInvoice.id)
        .filter(BaseInvoice.payment_method == CARD, BaseInvoice.status.in_(("pending", "expired")),
                CardCheckout.status == "open", BaseInvoice.created_at > floor)
        .order_by(CardCheckout.checked_at.asc().nullsfirst())
        .limit(SWEEP_BATCH)
        .all()
    )
    settled = 0
    for invoice in rows:
        try:
            if refresh_card(db, invoice, stripe=stripe, every_s=SWEEP_EVERY_S).status == "paid":
                settled += 1
        except (CardRefused, PayUnavailable) as exc:
            db.rollback()
            log.warning("card: sweep could not settle %s: %s", invoice.id, exc)
    return settled


# ------------------------------------------------------------------------------ reversals


def _end_access(db: Session, invoice: BaseInvoice, checkout: CardCheckout, kind: str, note: str) -> None:
    """The money went back, so what it bought stops: the key can no longer be redeemed and a
    workspace it opened drops to Expired. Data stays; the operator can restore by hand."""
    now = datetime.now(timezone.utc)
    checkout.status = kind
    checkout.note = note[:500]
    grant = db.query(DeskGrant).filter(DeskGrant.payment_ref == invoice.id).one_or_none()
    if grant is not None:
        grant.expires_at = now
        if grant.workspace_id:
            workspace = db.get(Workspace, grant.workspace_id)
            if workspace is not None:
                workspace.plan_expires_at = now
    invoice.status = kind
    invoice.desk_key = None
    db.commit()
    log.error("card: %s on %s — access ended (%s)", kind.upper(), invoice.id, note)


def _checkout_for_payment_intent(db: Session, payment_intent: str,
                                 stripe: StripeCall | None = None) -> CardCheckout | None:
    """A reversal names a payment intent. Before the paid event has been seen, the intent is
    not on any row yet, so ask Stripe which session it belongs to."""
    if not payment_intent:
        return None
    row = db.query(CardCheckout).filter(CardCheckout.payment_intent == payment_intent).one_or_none()
    if row is not None:
        return row
    stripe = stripe or _stripe_request
    try:
        status, found = stripe("GET", "/v1/checkout/sessions?" + urlencode({"payment_intent": payment_intent, "limit": 1}))
    except Exception:  # noqa: BLE001
        raise PayUnavailable("cannot associate the reversal yet") from None
    if status >= 300:
        raise PayUnavailable("cannot associate the reversal yet")
    for session in found.get("data") or []:
        row = db.query(CardCheckout).filter(CardCheckout.session_id == str(session.get("id") or "")).one_or_none()
        if row is not None and _payment_intent(session) == payment_intent:
            row.payment_intent = payment_intent
            db.commit()
            return row
    return None


def handle_webhook(db: Session, payload: bytes, signature: str, *, now: float | None = None,
                   stripe: StripeCall | None = None) -> dict[str, Any]:
    """A Stripe event, verified. Anything not about this desk's invoices is acknowledged and
    ignored, so Stripe does not retry it for days."""
    if not verify_signature(payload, signature, get_settings().stripe_webhook_secret.strip(), now=now):
        raise CardRefused("the Stripe-Signature does not verify")
    try:
        event = json.loads(payload)
    except ValueError:
        raise CardRefused("the event is not JSON") from None
    if not isinstance(event, dict):
        return {"outcome": "ignored"}
    kind = str(event.get("type") or "")
    obj = (event.get("data") or {}).get("object") or {}
    if not isinstance(obj, dict):
        return {"outcome": "ignored"}
    if kind in PAID_EVENTS or kind == "checkout.session.expired":
        invoice = db.get(BaseInvoice, str(obj.get("client_reference_id") or ""))
        checkout = db.get(CardCheckout, invoice.id) if invoice is not None else None
        if invoice is None or checkout is None or checkout.session_id != obj.get("id"):
            return {"outcome": "ignored"}
        if kind == "checkout.session.expired":
            if obj.get("payment_status") != "paid":
                _expire(db, invoice, checkout)
            return {"outcome": invoice.status, "invoice": invoice.id}
        try:
            invoice = settle_card(db, invoice, obj)
        except CardRefused as exc:
            # Acknowledged, not retried: a redelivery carries the same figures. It is logged
            # for the operator to look at in Stripe.
            return {"outcome": "refused", "invoice": invoice.id, "reason": str(exc)}
        return {"outcome": invoice.status, "invoice": invoice.id}
    if kind in ("charge.refunded", "charge.dispute.created"):
        checkout = _checkout_for_payment_intent(db, str(obj.get("payment_intent") or ""), stripe)
        if checkout is None:
            return {"outcome": "ignored"}
        invoice = db.get(BaseInvoice, checkout.invoice_id)
        if kind == "charge.dispute.created":
            _end_access(db, invoice, checkout, "disputed", f"dispute {str(obj.get('id'))[:40]}: {str(obj.get('reason'))[:60]}")
            return {"outcome": "disputed", "invoice": invoice.id}
        refunded = obj.get("amount_refunded")
        if isinstance(refunded, int) and refunded >= invoice.amount_raw:
            _end_access(db, invoice, checkout, "refunded", f"refunded {refunded} cents in Stripe")
            return {"outcome": "refunded", "invoice": invoice.id}
        checkout.note = f"partial refund {refunded} cents; access kept"
        db.commit()
        return {"outcome": "partial_refund", "invoice": invoice.id}
    return {"outcome": "ignored"}


# ----------------------------------------------------------------------------- rendering


def card_view(invoice: BaseInvoice, db: Session | None) -> dict:
    """The card half of `pay.invoice_view`: where to pay, and nothing about chains."""
    checkout = db.get(CardCheckout, invoice.id) if db is not None else None
    open_ = invoice.status == "pending" and checkout is not None and checkout.status == "open"
    return {
        "provider": "stripe-checkout",
        "checkout_url": checkout.checkout_url if open_ else None,
        "test_mode": bool(checkout is not None and not checkout.livemode),
        "state": checkout.status if checkout is not None else "failed",
    }


__all__ = [
    "CARD",
    "CardRefused",
    "card_closed_reason",
    "card_enabled",
    "card_public",
    "card_view",
    "create_card_invoice",
    "handle_webhook",
    "refresh_card",
    "settle_card",
    "sweep_card_invoices",
    "verify_signature",
]
