"""Emberline card checkout: a paid Stripe session becomes a desk key once, and nothing else does.

The same contract as the kernel desks (cite-desks/kernel/tests/test_card_checkout.py) on
Emberline's own models and routes. Stripe is faked; the sandbox run is in the commit message.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from app import basepay, card
from app.config import get_settings
from app.models import BaseInvoice, CardCheckout, DeskGrant, Workspace
from app.payfixture import get_fixture_rpc

TEST_KEY = "rk_test_" + "a" * 24
LIVE_KEY = "rk_live_" + "b" * 24
WHSEC = "whsec_" + "c" * 32
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


class FakeStripe:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.refuse = False

    def __call__(self, method: str, path: str, *, form=None, idempotency_key: str = ""):
        self.calls.append((method, path))
        if method == "POST" and path == "/v1/checkout/sessions":
            if self.refuse:
                return 400, {"error": {"message": "Invalid request"}}
            self.forms.append(form)
            sid = f"cs_test_{len(self.sessions) + 1:04d}" + "x" * 20
            self.sessions[sid] = {
                "id": sid, "url": f"https://checkout.stripe.com/c/pay/{sid}", "livemode": False,
                "status": "open", "payment_status": "unpaid", "client_reference_id": form["client_reference_id"],
                "currency": "usd", "amount_total": form["line_items"][0]["price_data"]["unit_amount"],
                "payment_intent": None,
            }
            return 200, dict(self.sessions[sid])
        if method == "GET" and path.startswith("/v1/checkout/sessions?"):
            pi = path.split("payment_intent=", 1)[1].split("&", 1)[0]
            return 200, {"data": [dict(s) for s in self.sessions.values() if s.get("payment_intent") == pi]}
        if method == "GET" and path.startswith("/v1/checkout/sessions/"):
            sid = path.rsplit("/", 1)[1]
            return (200, dict(self.sessions[sid])) if sid in self.sessions else (404, {})
        return 404, {}

    def pay(self, sid: str, **overrides) -> dict:
        self.sessions[sid].update(status="complete", payment_status="paid", payment_intent="pi_" + sid[-12:], **overrides)
        return dict(self.sessions[sid])


def _env(key: str = TEST_KEY, whsec: str = WHSEC, **extra: str) -> None:
    os.environ["STRIPE_SECRET_KEY"] = key
    os.environ["STRIPE_WEBHOOK_SECRET"] = whsec
    os.environ.update(extra)
    get_settings.cache_clear()


@pytest.fixture()
def stripe(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr(card, "_stripe_request", fake)
    _env()
    yield fake
    for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
        os.environ.pop(name, None)
    os.environ["APP_ENV"] = "test"
    os.environ["DESK_MODE"] = "live"
    get_settings.cache_clear()


def _deliver(client, kind: str, obj: dict, *, secret: str = WHSEC, stamp: int | None = None):
    body = json.dumps({"id": f"evt_{time.time_ns()}", "type": kind, "data": {"object": obj}}).encode()
    stamp = int(time.time()) if stamp is None else stamp
    sig = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return client.post("/api/public/pay/stripe/webhook", content=body,
                       headers={"Stripe-Signature": f"t={stamp},v1={sig}", "Content-Type": "application/json"})


def _order(client, plan: str = "solo") -> dict:
    res = client.post("/api/public/pay/orders", json={"plan": plan, "payment_method": "card_stripe"})
    assert res.status_code == 200, res.text
    return res.json()


def _sid(db, invoice_id: str) -> str:
    return db.get(CardCheckout, invoice_id).session_id


def test_card_method_is_listed_and_closed_without_keys(client) -> None:
    rail = client.get("/api/public/pay/status").json()
    method = next(m for m in rail["methods"] if m["id"] == "card_stripe")
    assert method["available"] is False and "STRIPE_SECRET_KEY" in method["reason"]
    assert rail["card"]["enabled"] is False
    res = client.post("/api/public/pay/orders", json={"plan": "solo", "payment_method": "card_stripe"})
    assert res.status_code == 503
    assert client.post("/api/public/pay/stripe/webhook", content=b"{}").status_code == 404


def test_demo_desk_keeps_card_closed_even_with_keys(stripe, client) -> None:
    _env(DESK_MODE="demo")
    rail = client.get("/api/public/pay/status").json()
    assert rail["card"]["enabled"] is False and "demo mode" in rail["card"]["closed_reason"]
    assert client.post("/api/public/pay/orders", json={"plan": "solo", "payment_method": "card_stripe"}).status_code == 503
    assert stripe.calls == []


def test_key_mode_must_match_the_environment(stripe) -> None:
    _env(key=LIVE_KEY)
    assert "live key outside production" in card.card_closed_reason()
    _env(key=TEST_KEY, APP_ENV="production")
    assert "test key on a production desk" in card.card_closed_reason()


def test_order_opens_a_session_for_the_plan_price(stripe, client, db) -> None:
    rail = client.get("/api/public/pay/status").json()
    assert next(m for m in rail["methods"] if m["id"] == "card_stripe")["available"] is True
    invoice = _order(client, "team")
    assert invoice["payment_method"] == "card_stripe" and invoice["amount_usd"] == 149
    assert invoice["card"]["checkout_url"].startswith("https://checkout.stripe.com/")
    assert "pay_to" not in invoice and "eip681" not in invoice
    form = stripe.forms[0]
    assert form["line_items"][0]["price_data"]["unit_amount"] == 14900
    assert form["success_url"] == f"{get_settings().public_url.rstrip('/')}/pay/{invoice['id']}?card=return"
    assert form["payment_method_types"] == ["card"]


def test_webhook_settles_once_and_the_key_redeems(stripe, client, db) -> None:
    invoice = _order(client)
    paid = stripe.pay(_sid(db, invoice["id"]))
    assert _deliver(client, "checkout.session.completed", paid).json()["outcome"] == "paid"
    assert _deliver(client, "checkout.session.completed", paid).json()["outcome"] == "paid"
    assert db.query(DeskGrant).filter(DeskGrant.payment_ref == invoice["id"]).count() == 1
    view = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()
    assert view["status"] == "paid" and view["desk_key"]
    redeemed = client.post("/api/auth/redeem", json={"desk_key": view["desk_key"]})
    assert redeemed.status_code == 200
    assert redeemed.json()["user"]["workspace"]["plan"] == "solo"


def test_refresh_and_sweep_settle_without_the_webhook(stripe, client, db) -> None:
    first = _order(client)
    second = _order(client, "desk")
    stripe.pay(_sid(db, first["id"]))
    assert client.post(f"/api/public/pay/invoices/{first['id']}/card/refresh").json()["status"] == "paid"
    stripe.pay(_sid(db, second["id"]))
    assert card.sweep_card_invoices(db) == 1
    db.expire_all()
    assert db.get(BaseInvoice, second["id"]).status == "paid"


def test_signature_amount_and_session_are_checked(stripe, client, db) -> None:
    invoice = _order(client, "desk")
    sid = _sid(db, invoice["id"])
    paid = stripe.pay(sid)
    assert _deliver(client, "checkout.session.completed", paid, secret="whsec_wrong").status_code == 400
    assert _deliver(client, "checkout.session.completed", paid, stamp=int(time.time()) - 3600).status_code == 400
    assert _deliver(client, "checkout.session.completed", {**paid, "amount_total": 100}).json()["outcome"] == "refused"
    assert _deliver(client, "checkout.session.completed", {**paid, "currency": "eur"}).json()["outcome"] == "refused"
    assert _deliver(client, "checkout.session.completed", {**paid, "id": "cs_test_other"}).json()["outcome"] == "ignored"
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["status"] == "pending"


def test_usdc_cannot_settle_a_card_invoice(stripe, client, db) -> None:
    invoice = _order(client)
    rpc = get_fixture_rpc()
    rpc.inject_usdc_transfer(token=USDC, pay_to=basepay.treasury(), amount_raw=4900)
    basepay.scan_payments(db, rpc=rpc)
    db.expire_all()
    assert db.get(BaseInvoice, invoice["id"]).status == "pending"
    tx = "0x" + "ab" * 32
    assert client.post(f"/api/public/pay/invoices/{invoice['id']}/confirm", json={"tx_hash": tx}).status_code == 409
    assert client.post(f"/api/public/pay/invoices/{invoice['id']}/simulate").status_code == 409


def test_refund_and_dispute_end_access(stripe, client, db) -> None:
    invoice = _order(client)
    paid = stripe.pay(_sid(db, invoice["id"]))
    _deliver(client, "checkout.session.completed", paid)
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    assert client.post("/api/auth/redeem", json={"desk_key": key}).status_code == 200
    partial = _deliver(client, "charge.refunded", {"id": "ch_1", "payment_intent": paid["payment_intent"], "amount_refunded": 900})
    assert partial.json()["outcome"] == "partial_refund"
    full = _deliver(client, "charge.refunded", {"id": "ch_1", "payment_intent": paid["payment_intent"], "amount_refunded": 4900})
    assert full.json()["outcome"] == "refunded"
    db.expire_all()
    grant = db.query(DeskGrant).filter(DeskGrant.payment_ref == invoice["id"]).one()
    exp = db.get(Workspace, grant.workspace_id).plan_expires_at
    assert (exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)) <= datetime.now(timezone.utc) + timedelta(seconds=1)
    assert client.post("/api/auth/redeem", json={"desk_key": key}).status_code == 410


def test_a_refund_that_overtakes_the_paid_event_blocks_the_key(stripe, client, db) -> None:
    invoice = _order(client)
    paid = stripe.pay(_sid(db, invoice["id"]))
    assert _deliver(client, "charge.refunded", {"id": "ch_1", "payment_intent": paid["payment_intent"],
                                                "amount_refunded": 4900}).json()["outcome"] == "refunded"
    assert _deliver(client, "checkout.session.completed", paid).json()["outcome"] == "refused"
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"] is None


def test_stripe_refusal_charges_nothing(stripe, client) -> None:
    stripe.refuse = True
    res = client.post("/api/public/pay/orders", json={"plan": "solo", "payment_method": "card_stripe"})
    assert res.status_code == 503 and "nothing was charged" in res.json()["detail"]


def test_card_invoice_pdf_and_ops_count_dollars(stripe, client, db) -> None:
    invoice = _order(client, "team")
    pdf = client.get(f"/api/public/pay/invoices/{invoice['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    paid = stripe.pay(_sid(db, invoice["id"]))
    _deliver(client, "checkout.session.completed", paid)
    from app.ops import dashboard  # noqa: PLC0415 - the ops module reads the whole database

    kpis = dashboard(db)["kpis"]
    assert kpis["card_paid_usd"] == 149.0
    assert kpis["usdc_paid"] == 0
