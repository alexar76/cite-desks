"""Card checkout must end in a desk key with nobody in the loop, and never grant on a guess.

The buyer opens a Stripe Checkout Session through the desk, pays on Stripe's page, and the
desk turns the paid session into the same desk key a USDC transfer buys — by webhook, by a
refresh when the buyer comes back first, or by the scheduled sweep when both were lost.
Stripe is faked here; the real sandbox run is in the commit message of this change.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["HUB_MODE"] = "fixture"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO"] = "true"
os.environ["JWT_SECRET"] = "test-secret-must-be-at-least-32b"
os.environ["PAY_MODE"] = "fixture"
os.environ.setdefault("DESK_MODE", "live")
os.environ["DESK_ID"] = "tideline"

from desk_kernel.demo import DEMO_CHECKOUT_CLOSED
from desk_kernel.service import card, pay
from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.service.db import Base, SessionLocal, engine
from desk_kernel.service.main import create_app
from desk_kernel.service.models import BaseInvoice, CardCheckout, DeskGrant, Workspace
from desk_kernel.service.payfixture import get_fixture_rpc, reset_fixture_rpc
from desk_kernel.service.security import reset_rate_limits
from desk_kernel.service.seed import seed_demo

TEST_KEY = "rk_test_" + "a" * 24
LIVE_KEY = "rk_live_" + "b" * 24
WHSEC = "whsec_" + "c" * 32
STRIPE_ENV = ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "PUBLIC_URL")


class FakeStripe:
    """Checkout Sessions as Stripe keeps them, enough for the desk's three calls."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.keys: list[str] = []
        self.refuse = False

    def __call__(self, method: str, path: str, *, form=None, idempotency_key: str = ""):
        self.calls.append((method, path))
        if method == "POST" and path == "/v1/checkout/sessions":
            if self.refuse:
                return 400, {"error": {"message": "Invalid request"}}
            self.forms.append(form)
            self.keys.append(idempotency_key)
            sid = f"cs_test_{len(self.sessions) + 1:04d}" + "x" * 20
            session = {
                "id": sid,
                "object": "checkout.session",
                "url": f"https://checkout.stripe.com/c/pay/{sid}",
                "livemode": False,
                "status": "open",
                "payment_status": "unpaid",
                "client_reference_id": form["client_reference_id"],
                "metadata": form["metadata"],
                "currency": "usd",
                "amount_total": form["line_items"][0]["price_data"]["unit_amount"],
                "payment_intent": None,
            }
            self.sessions[sid] = session
            return 200, dict(session)
        if method == "GET" and path.startswith("/v1/checkout/sessions?"):
            pi = path.split("payment_intent=", 1)[1].split("&", 1)[0]
            return 200, {"data": [dict(s) for s in self.sessions.values() if s.get("payment_intent") == pi]}
        if method == "GET" and path.startswith("/v1/checkout/sessions/"):
            sid = path.rsplit("/", 1)[1]
            if sid not in self.sessions:
                return 404, {"error": {"message": "No such checkout.session"}}
            return 200, dict(self.sessions[sid])
        return 404, {}

    def pay(self, sid: str, **overrides) -> dict:
        """What Stripe's hosted page does when the buyer's card is accepted."""
        session = self.sessions[sid]
        session.update(status="complete", payment_status="paid", payment_intent="pi_" + sid[-12:], **overrides)
        return dict(session)


def _reset(*, key: str = TEST_KEY, whsec: str = WHSEC, desk_mode: str = "live", app_env: str = "test") -> None:
    os.environ["DESK_ID"] = "tideline"
    os.environ["PAY_MODE"] = "fixture"
    os.environ["PAY_BASE_ADDRESS"] = ""
    os.environ["DESK_MODE"] = desk_mode
    os.environ["APP_ENV"] = app_env
    os.environ["STRIPE_SECRET_KEY"] = key
    os.environ["STRIPE_WEBHOOK_SECRET"] = whsec
    os.environ["PUBLIC_URL"] = "https://tideline.example"
    get_settings.cache_clear()
    current_claim.cache_clear()
    reset_fixture_rpc()
    reset_rate_limits()
    pay._rpc_cache = None
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


def _clear() -> None:
    for name in STRIPE_ENV:
        os.environ.pop(name, None)
    os.environ["APP_ENV"] = "test"
    os.environ["DESK_MODE"] = "live"
    get_settings.cache_clear()


@pytest.fixture()
def stripe(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr(card, "_stripe_request", fake)
    return fake


@pytest.fixture()
def client(stripe):
    _reset()
    with TestClient(create_app("tideline")) as test_client:
        yield test_client
    _clear()


def _signed(event: dict, *, secret: str = WHSEC, stamp: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    stamp = int(time.time()) if stamp is None else stamp
    sig = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={stamp},v1={sig}", "Content-Type": "application/json"}


def _event(kind: str, obj: dict) -> dict:
    return {"id": "evt_" + str(time.time_ns()), "type": kind, "livemode": False, "data": {"object": obj}}


def _deliver(client: TestClient, kind: str, obj: dict, **kw):
    body, headers = _signed(_event(kind, obj), **kw)
    return client.post("/api/public/pay/stripe/webhook", content=body, headers=headers)


def _open(client: TestClient, plan: str = "solo") -> dict:
    res = client.post("/api/public/pay/card", json={"plan": plan})
    assert res.status_code == 200, res.text
    return res.json()


def _session_id(invoice_id: str) -> str:
    db = SessionLocal()
    try:
        return db.get(CardCheckout, invoice_id).session_id
    finally:
        db.close()


# ------------------------------------------------------------------------------ rail state


def test_card_is_closed_without_keys(stripe) -> None:
    _reset(key="", whsec="")
    try:
        with TestClient(create_app("tideline")) as client:
            rail = client.get("/api/public/pay/status").json()
            assert rail["card"]["enabled"] is False
            assert "STRIPE_SECRET_KEY" in rail["card"]["closed_reason"]
            assert client.post("/api/public/pay/card", json={"plan": "solo"}).status_code == 503
            # No secret, no endpoint: an unconfigured desk does not advertise a webhook.
            assert client.post("/api/public/pay/stripe/webhook", content=b"{}").status_code == 404
    finally:
        _clear()
    assert stripe.calls == []


def test_demo_desk_keeps_card_closed_even_with_keys(stripe) -> None:
    _reset(desk_mode="demo")
    try:
        with TestClient(create_app("tideline")) as client:
            status = client.get("/api/public/status").json()
            assert status["demo"] is True
            rail = client.get("/api/public/pay/status").json()
            assert rail["enabled"] is False
            assert rail["card"] == {**rail["card"], "enabled": False, "closed_reason": DEMO_CHECKOUT_CLOSED}
            res = client.post("/api/public/pay/card", json={"plan": "solo"})
            assert res.status_code == 503
            assert "demo mode" in res.json()["detail"]
    finally:
        _clear()
    assert stripe.calls == []


def test_a_test_key_never_opens_on_a_production_desk() -> None:
    _reset(key=TEST_KEY)
    try:
        os.environ["APP_ENV"] = "production"
        get_settings.cache_clear()
        assert "test key on a production desk" in card.card_closed_reason()
    finally:
        _clear()


def test_a_live_key_never_opens_outside_production() -> None:
    _reset(key=LIVE_KEY)
    try:
        assert "live key outside production" in card.card_closed_reason()
        assert card.card_enabled() is False
    finally:
        _clear()


def test_a_key_that_is_not_stripe_keeps_card_closed() -> None:
    _reset(key="pk_test_publishable")
    try:
        assert "not a Stripe secret" in card.card_closed_reason()
    finally:
        _clear()


# ------------------------------------------------------------------------------ happy path


def test_open_card_checkout_quotes_the_plan_price_in_cents(client, stripe) -> None:
    rail = client.get("/api/public/pay/status").json()
    assert rail["card"]["enabled"] is True and rail["card"]["test_mode"] is True
    invoice = _open(client, "team")
    assert invoice["payment_method"] == "card_stripe"
    assert invoice["status"] == "pending"
    assert invoice["amount_usd"] == 149
    assert invoice["card"]["checkout_url"].startswith("https://checkout.stripe.com/")
    assert "pay_to" not in invoice and "eip681" not in invoice
    form = stripe.forms[0]
    price = form["line_items"][0]["price_data"]
    assert price["unit_amount"] == 14900 and price["currency"] == "usd"
    assert form["client_reference_id"] == invoice["id"]
    assert form["success_url"] == f"https://tideline.example/pay/{invoice['id']}?card=return"
    assert form["payment_method_types"] == ["card"]
    # Stripe's expiry window is 30 min .. 24 h; the session must be inside it.
    lasts = form["expires_at"] - int(time.time())
    assert 30 * 60 < lasts < 24 * 3600
    assert stripe.keys == [invoice["id"]]


def test_webhook_turns_a_paid_session_into_a_key_once(client, stripe) -> None:
    invoice = _open(client)
    paid = stripe.pay(_session_id(invoice["id"]))
    first = _deliver(client, "checkout.session.completed", paid)
    assert first.status_code == 200 and first.json()["outcome"] == "paid"
    again = _deliver(client, "checkout.session.completed", paid)
    assert again.status_code == 200 and again.json()["outcome"] == "paid"
    view = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()
    assert view["status"] == "paid" and view["desk_key"]
    assert view["card"]["checkout_url"] is None
    db = SessionLocal()
    try:
        assert db.query(DeskGrant).filter(DeskGrant.payment_ref == invoice["id"]).count() == 1
    finally:
        db.close()
    redeemed = client.post("/api/auth/redeem", json={"desk_key": view["desk_key"]})
    assert redeemed.status_code == 200
    assert redeemed.json()["user"]["workspace"]["plan"] == "solo"
    # Redeemed: the key is no longer shown to whoever holds the invoice link.
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"] is None


def test_refresh_settles_when_the_buyer_is_back_before_the_webhook(client, stripe) -> None:
    invoice = _open(client)
    pending = client.post(f"/api/public/pay/invoices/{invoice['id']}/card/refresh").json()
    assert pending["status"] == "pending"
    stripe.pay(_session_id(invoice["id"]))
    # Rationed: a second read inside five seconds does not reach Stripe.
    reads = len(stripe.calls)
    assert client.post(f"/api/public/pay/invoices/{invoice['id']}/card/refresh").json()["status"] == "pending"
    assert len(stripe.calls) == reads
    db = SessionLocal()
    try:
        row = db.get(CardCheckout, invoice["id"])
        row.checked_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        db.commit()
    finally:
        db.close()
    done = client.post(f"/api/public/pay/invoices/{invoice['id']}/card/refresh").json()
    assert done["status"] == "paid" and done["desk_key"]


def test_sweep_settles_a_closed_tab_with_a_lost_webhook(client, stripe) -> None:
    paid_invoice = _open(client)
    lapsed_invoice = _open(client, "desk")
    stripe.pay(_session_id(paid_invoice["id"]))
    stripe.sessions[_session_id(lapsed_invoice["id"])]["status"] = "expired"
    db = SessionLocal()
    try:
        assert card.sweep_card_invoices(db) == 1
        assert db.get(BaseInvoice, paid_invoice["id"]).status == "paid"
        assert db.get(BaseInvoice, lapsed_invoice["id"]).status == "expired"
        assert db.get(CardCheckout, lapsed_invoice["id"]).status == "expired"
    finally:
        db.close()


def test_a_session_paid_after_the_quote_lapsed_is_still_honoured(client, stripe) -> None:
    invoice = _open(client)
    db = SessionLocal()
    try:
        row = db.get(BaseInvoice, invoice["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["status"] == "expired"
    paid = stripe.pay(_session_id(invoice["id"]))
    assert _deliver(client, "checkout.session.completed", paid).json()["outcome"] == "paid"


# ------------------------------------------------------------------------- what must fail


def test_webhook_signature_is_required_and_fresh(client, stripe) -> None:
    invoice = _open(client)
    paid = stripe.pay(_session_id(invoice["id"]))
    assert _deliver(client, "checkout.session.completed", paid, secret="whsec_wrong").status_code == 400
    assert _deliver(client, "checkout.session.completed", paid, stamp=int(time.time()) - 3600).status_code == 400
    unsigned = client.post("/api/public/pay/stripe/webhook", content=json.dumps(_event("checkout.session.completed", paid)))
    assert unsigned.status_code == 400
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["status"] == "pending"


def test_an_event_cannot_choose_the_amount(client, stripe) -> None:
    invoice = _open(client, "desk")
    paid = stripe.pay(_session_id(invoice["id"]), amount_total=100)
    res = _deliver(client, "checkout.session.completed", paid)
    assert res.status_code == 200 and res.json()["outcome"] == "refused"
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["status"] == "pending"
    other_currency = stripe.pay(_session_id(invoice["id"]), amount_total=49900, currency="eur")
    assert _deliver(client, "checkout.session.completed", other_currency).json()["outcome"] == "refused"


def test_an_event_for_another_session_does_not_settle_this_invoice(client, stripe) -> None:
    invoice = _open(client)
    forged = {**stripe.pay(_session_id(invoice["id"])), "id": "cs_test_somebody_else"}
    assert _deliver(client, "checkout.session.completed", forged).json()["outcome"] == "ignored"
    unpaid = {**stripe.sessions[_session_id(invoice["id"])], "payment_status": "unpaid"}
    assert _deliver(client, "checkout.session.completed", unpaid).json()["outcome"] == "pending"
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["status"] == "pending"


def test_a_usdc_transfer_of_the_cents_figure_never_settles_a_card_invoice(client, stripe) -> None:
    invoice = _open(client)
    rpc = get_fixture_rpc()
    rpc.inject_usdc_transfer(token=get_settings().pay_usdc_address, pay_to=pay.treasury(), amount_raw=4900)
    db = SessionLocal()
    try:
        pay.scan_payments(db, rpc=rpc)
        assert db.get(BaseInvoice, invoice["id"]).status == "pending"
    finally:
        db.close()
    tx = "0x" + "ab" * 32
    assert client.post(f"/api/public/pay/invoices/{invoice['id']}/confirm", json={"tx_hash": tx}).status_code == 409
    assert client.post(f"/api/public/pay/invoices/{invoice['id']}/simulate").status_code == 409


def test_stripe_refusing_the_session_charges_nothing(client, stripe) -> None:
    stripe.refuse = True
    res = client.post("/api/public/pay/card", json={"plan": "solo"})
    assert res.status_code == 503
    assert "nothing was charged" in res.json()["detail"]
    db = SessionLocal()
    try:
        assert {row.status for row in db.query(BaseInvoice).filter(BaseInvoice.payment_method == "card_stripe")} == {"failed"}
    finally:
        db.close()


def test_a_live_desk_refuses_a_test_mode_payment(stripe) -> None:
    _reset(key=TEST_KEY)
    try:
        db = SessionLocal()
        invoice = card.create_card_invoice(db, plan="solo", stripe=stripe)
        paid = stripe.pay(_session_id(invoice.id))
        os.environ["STRIPE_SECRET_KEY"] = LIVE_KEY
        get_settings.cache_clear()
        with pytest.raises(card.CardRefused):
            card.settle_card(db, invoice, paid)
        assert db.get(BaseInvoice, invoice.id).status == "pending"
        db.close()
    finally:
        _clear()


# ------------------------------------------------------------------------------- reversals


def _paid_and_redeemed(client, stripe) -> tuple[dict, str]:
    invoice = _open(client)
    paid = stripe.pay(_session_id(invoice["id"]))
    _deliver(client, "checkout.session.completed", paid)
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    return invoice, key


def test_a_full_refund_ends_the_access_it_bought(client, stripe) -> None:
    invoice, key = _paid_and_redeemed(client, stripe)
    assert client.post("/api/auth/redeem", json={"desk_key": key}).status_code == 200
    pi = stripe.sessions[_session_id(invoice["id"])]["payment_intent"]
    res = _deliver(client, "charge.refunded", {"id": "ch_1", "payment_intent": pi, "amount_refunded": 4900})
    assert res.json()["outcome"] == "refunded"
    db = SessionLocal()
    try:
        grant = db.query(DeskGrant).filter(DeskGrant.payment_ref == invoice["id"]).one()
        workspace = db.get(Workspace, grant.workspace_id)
        assert pay._aware(workspace.plan_expires_at) <= datetime.now(timezone.utc)
    finally:
        db.close()
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["status"] == "refunded"


def test_a_partial_refund_keeps_access_and_an_unredeemed_key_dies_on_dispute(client, stripe) -> None:
    invoice, key = _paid_and_redeemed(client, stripe)
    pi = stripe.sessions[_session_id(invoice["id"])]["payment_intent"]
    partial = _deliver(client, "charge.refunded", {"id": "ch_1", "payment_intent": pi, "amount_refunded": 900})
    assert partial.json()["outcome"] == "partial_refund"
    dispute = _deliver(client, "charge.dispute.created", {"id": "dp_1", "payment_intent": pi, "reason": "fraudulent"})
    assert dispute.json()["outcome"] == "disputed"
    assert client.post("/api/auth/redeem", json={"desk_key": key}).status_code == 410


def test_a_refund_that_overtakes_the_paid_event_still_blocks_the_key(client, stripe) -> None:
    invoice = _open(client)
    paid = stripe.pay(_session_id(invoice["id"]))
    refund = _deliver(client, "charge.refunded", {"id": "ch_1", "payment_intent": paid["payment_intent"], "amount_refunded": 4900})
    assert refund.json()["outcome"] == "refunded"
    late = _deliver(client, "checkout.session.completed", paid)
    assert late.json()["outcome"] == "refused"
    view = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()
    assert view["status"] == "refunded" and view["desk_key"] is None


def test_an_unknown_reversal_is_acknowledged(client, stripe) -> None:
    res = _deliver(client, "charge.refunded", {"id": "ch_x", "payment_intent": "pi_not_ours", "amount_refunded": 100})
    assert res.status_code == 200 and res.json()["outcome"] == "ignored"
    assert _deliver(client, "customer.created", {"id": "cus_1"}).json()["outcome"] == "ignored"


def test_health_says_whether_card_checkout_is_open(client) -> None:
    health = client.get("/api/public/health").json()
    assert health["checkout"]["card"] == {"open": True, "reason": ""}
