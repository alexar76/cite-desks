from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.basepay import (
    FailoverRpc,
    RpcError,
    Transfer,
    confirm_invoice,
    eip681,
    fixture_allowed,
    format_usdc,
    match_invoice,
    parse_transfer_logs,
    rail_enabled,
    rpc_urls,
    settle,
    topic_address,
)
from app.config import Settings, parse_rpc_urls
from app.models import BaseInvoice
from app.security import new_id


TREASURY = "0x1111111111111111111111111111111111111111"  # the fixture desk's stand-in
LIVE_TREASURY = "0x" + "de" * 20                          # stands for a wallet we own
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def test_the_chain_layer_is_the_kernels_and_not_a_second_copy() -> None:
    """One implementation of the Base rail, or a bug fixed here stays open in three desks.

    This is not style. The two copies drifted the day after they were split: the kernel's
    endpoint-list parser did not split on `;` while Emberline's did, so the same
    PAY_BASE_RPC_URL produced a different RPC list per desk.
    """
    from desk_kernel import chain

    from app import basepay
    from app.config import parse_rpc_urls as config_parse

    for name in ("Transfer", "RpcError", "FailoverRpc", "parse_transfer_logs", "format_usdc",
                 "topic_address", "eip681", "explorer_base", "normalize_address"):
        assert getattr(basepay, name) is getattr(chain, name), f"{name} forked from the kernel"
    assert config_parse is chain.parse_rpc_urls
    # The scan must be the kernel's walk, not a local re-implementation of the windowing.
    assert not hasattr(basepay, "_fetch_window")
    assert not hasattr(basepay, "_RANGE_REFUSALS")
    assert basepay.LOG_WINDOW_BLOCKS == chain.LOG_WINDOW_BLOCKS


def test_the_fixture_chain_is_the_kernels_too() -> None:
    from desk_kernel.service import payfixture as kernel_fixture

    from app import payfixture

    assert payfixture.FixtureRpc is kernel_fixture.FixtureRpc
    assert payfixture.get_fixture_rpc() is kernel_fixture.get_fixture_rpc()


def test_format_and_eip681() -> None:
    assert format_usdc(49_000123) == "49.000123"
    link = eip681(token=USDC, chain_id=8453, to=TREASURY, amount_raw=49_000123)
    assert link.startswith("ethereum:0x833589")
    assert "8453/transfer" in link
    assert "uint256=49000123" in link


def test_rail_disabled_without_address() -> None:
    assert not rail_enabled(Settings.model_construct(pay_mode="live", pay_base_rpc_url="https://x", pay_base_address=""))
    # An empty PAY_BASE_RPC_URL is fine: the built-in public Base endpoints follow.
    assert rail_enabled(
        Settings.model_construct(pay_mode="live", pay_base_rpc_url="", pay_base_address=LIVE_TREASURY)
    )
    assert rail_enabled(
        Settings.model_construct(pay_mode="live", pay_base_rpc_url="https://example.invalid", pay_base_address=LIVE_TREASURY)
    )
    assert rail_enabled(
        Settings.model_construct(pay_mode="fixture", app_env="development", pay_base_rpc_url="", pay_base_address=TREASURY)
    )
    # PAY_MODE=fixture does not survive production, so this desk is live — with the
    # placeholder treasury. It must refuse to quote: an invoice pointing there sends a
    # customer's USDC to a wallet nobody owns, and no scan can ever settle it.
    prod_fixture = Settings.model_construct(pay_mode="fixture", app_env="production", pay_base_rpc_url="", pay_base_address=TREASURY)
    assert not fixture_allowed(prod_fixture)
    assert not rail_enabled(prod_fixture)
    from app.basepay import rail_closed_reason

    assert "placeholder" in rail_closed_reason(prod_fixture)


def test_parse_rpc_urls_and_backups() -> None:
    assert parse_rpc_urls("https://a.example, https://b.example;https://a.example") == [
        "https://a.example",
        "https://b.example",
    ]
    urls = rpc_urls(Settings.model_construct(pay_base_rpc_url="https://custom.example/rpc"))
    assert urls[0] == "https://custom.example/rpc"
    assert "https://mainnet.base.org" in urls
    assert "https://base-rpc.publicnode.com" in urls


class _Boom:
    def __init__(self) -> None:
        self.n = 0

    def call(self, method: str, params: list) -> object:
        self.n += 1
        raise RpcError("down")


class _Ok:
    def __init__(self, value: object = "0x1") -> None:
        self.n = 0
        self.value = value

    def call(self, method: str, params: list) -> object:
        self.n += 1
        return self.value


def test_rpc_failover_is_sticky() -> None:
    boom, ok = _Boom(), _Ok()
    rpc = FailoverRpc(["https://dead", "https://live"], clients=[boom, ok])
    assert rpc.call("eth_blockNumber", []) == "0x1"
    assert boom.n == 1 and ok.n == 1
    assert rpc.call("eth_blockNumber", []) == "0x1"
    assert boom.n == 1 and ok.n == 2


def test_rpc_failover_all_down() -> None:
    rpc = FailoverRpc(["https://a", "https://b"], clients=[_Boom(), _Boom()])
    try:
        rpc.call("eth_blockNumber", [])
    except RpcError as exc:
        assert "all rpc endpoints failed" in str(exc)
    else:
        raise AssertionError("expected RpcError")


def test_parse_transfer_to_treasury() -> None:
    logs = [
        {
            "address": USDC,
            "topics": [
                TRANSFER,
                "0x" + "aa" * 32,
                topic_address(TREASURY),
            ],
            "data": hex(49_000007),
            "transactionHash": "0x" + "ab" * 32,
            "blockNumber": hex(100),
            "logIndex": "0x1",
        }
    ]
    rows = parse_transfer_logs(logs, token=USDC, pay_to=TREASURY)
    assert len(rows) == 1
    assert rows[0].amount_raw == 49_000007
    assert rows[0].to == TREASURY


def test_invoice_create_and_settle(client, db) -> None:
    status = client.get("/api/public/pay/status").json()
    assert status["enabled"] is True
    assert status["chain_id"] == 8453
    created = client.post("/api/public/pay/invoices", json={"plan": "solo"})
    assert created.status_code == 200
    body = created.json()
    assert body["token"] == "USDC"
    assert body["chain_id"] == 8453
    assert body["number"].startswith("EL-")
    assert body["payment_method"] == "usdc_base"
    assert body["line_items"][0]["amount_usd"] == 49
    assert body["amount_usdc"].startswith("49.")
    assert body["desk_key"] is None
    assert client.get(f"/api/public/pay/invoices/{body['id']}/pdf").headers["content-type"].startswith("application/pdf")
    blocked = client.post("/api/public/pay/orders", json={"plan": "solo", "payment_method": "card"})
    assert blocked.status_code == 422
    invoice = db.get(BaseInvoice, body["id"])
    assert invoice is not None
    transfer = Transfer(
        tx_hash="0x" + "cd" * 32,
        frm="0x" + "aa" * 20,
        to=invoice.pay_to,
        amount_raw=invoice.amount_raw,
        block_number=10,
        log_index=0,
    )
    assert match_invoice(db, transfer) is invoice
    paid = settle(db, invoice, transfer)
    assert paid.status == "paid"
    assert paid.desk_key and paid.desk_key.startswith("emb_")
    view = client.get(f"/api/public/pay/invoices/{body['id']}").json()
    assert view["desk_key"] == paid.desk_key
    redeemed = client.post("/api/auth/redeem", json={"desk_key": paid.desk_key})
    assert redeemed.status_code == 200
    hidden = client.get(f"/api/public/pay/invoices/{body['id']}").json()
    assert hidden["desk_key"] is None
    assert hidden["status"] == "paid"


def test_wrong_amount_does_not_match(db) -> None:
    invoice = BaseInvoice(
        id=new_id("inv"),
        plan="solo",
        days=30,
        amount_raw=49_000042,
        status="pending",
        pay_to=TREASURY,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(invoice)
    db.commit()
    transfer = Transfer(
        tx_hash="0x" + "ee" * 32,
        frm="0x" + "bb" * 20,
        to=TREASURY,
        amount_raw=49_000000,
        block_number=1,
        log_index=0,
    )
    assert match_invoice(db, transfer) is None


class _FakeRpc:
    def __init__(self, receipt: dict, head: int, block_time: datetime | None = None) -> None:
        self.receipt = receipt
        self.head = head
        self.block_time = block_time or datetime.now(timezone.utc)

    def call(self, method: str, params: list) -> object:
        if method == "eth_getTransactionReceipt":
            return self.receipt
        if method == "eth_blockNumber":
            return hex(self.head)
        if method == "eth_getBlockByNumber":
            return {"timestamp": hex(int(self.block_time.timestamp()))}
        raise AssertionError(method)


def test_confirm_requires_exact_usdc_and_confirmations(db) -> None:
    invoice = BaseInvoice(
        id=new_id("inv"),
        plan="team",
        days=30,
        amount_raw=149_000088,
        status="pending",
        pay_to=TREASURY,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(invoice)
    db.commit()
    tx = "0x" + "11" * 32
    receipt = {
        "status": "0x1",
        "blockNumber": hex(50),
        "logs": [
            {
                "address": USDC,
                "topics": [TRANSFER, "0x" + "aa" * 32, topic_address(TREASURY)],
                "data": hex(149_000088),
                "transactionHash": tx,
                "blockNumber": hex(50),
                "logIndex": "0x0",
            }
        ],
    }
    early = _FakeRpc(receipt, head=50)
    try:
        confirm_invoice(db, invoice, tx, rpc=early)
        raise AssertionError("expected confirmations error")
    except ValueError as exc:
        assert "confirmations" in str(exc)
    paid = confirm_invoice(db, invoice, tx, rpc=_FakeRpc(receipt, head=60))
    assert paid.status == "paid"
    assert paid.desk_key.startswith("emb_")


def test_full_http_order_simulate_redeem(client) -> None:
    status = client.get("/api/public/pay/status").json()
    assert status["enabled"] is True
    assert status["fixture"] is True
    created = client.post("/api/public/pay/orders", json={"plan": "solo", "payment_method": "usdc_base"})
    assert created.status_code == 200
    invoice_id = created.json()["id"]
    amount = created.json()["amount_usdc"]
    assert amount != "49.000000"
    simulated = client.post(f"/api/public/pay/invoices/{invoice_id}/simulate")
    assert simulated.status_code == 200
    body = simulated.json()
    assert body["status"] == "paid"
    assert body["tx_hash"]
    assert body["desk_key"].startswith("emb_")
    replay = client.post(f"/api/public/pay/invoices/{invoice_id}/simulate")
    assert replay.status_code == 200
    redeemed = client.post("/api/auth/redeem", json={"desk_key": body["desk_key"]})
    assert redeemed.status_code == 200
    user = redeemed.json()["user"]
    assert user["workspace"]["plan"] == "solo"
    assert user["workspace"]["plan_expired"] is False
    assert user["workspace"]["plan_expires_at"]
    after = client.get(f"/api/public/pay/invoices/{invoice_id}").json()
    assert after["desk_key"] is None
    token = redeemed.json()["access_token"]
    usage = client.get("/api/billing/usage", headers={"Authorization": f"Bearer {token}"}).json()
    assert usage["plan"] == "solo"
    assert usage["plan_expired"] is False


def test_unique_pending_amounts(client) -> None:
    first = client.post("/api/public/pay/orders", json={"plan": "team", "payment_method": "usdc_base"}).json()
    second = client.post("/api/public/pay/orders", json={"plan": "team", "payment_method": "usdc_base"}).json()
    assert first["amount_raw"] != second["amount_raw"]
    assert first["amount_usdc"].startswith("149.")


def test_scan_settles_injected_transfer(client, db) -> None:
    from app.basepay import scan_payments
    from app.payfixture import get_fixture_rpc

    created = client.post("/api/public/pay/orders", json={"plan": "desk", "payment_method": "usdc_base"}).json()
    invoice = db.get(BaseInvoice, created["id"])
    assert invoice is not None
    rpc = get_fixture_rpc()
    rpc.inject_usdc_transfer(token=USDC, pay_to=invoice.pay_to, amount_raw=invoice.amount_raw)
    settled = scan_payments(db, rpc=rpc)
    assert settled == 1
    db.refresh(invoice)
    assert invoice.status == "paid"


def test_expired_plan_blocks_new_watch(client, db) -> None:
    from datetime import datetime, timedelta, timezone

    from app.models import Workspace

    minted = client.post(
        "/api/pay/mint",
        json={"plan": "solo", "days": 30, "payment_ref": "wire-expired"},
        headers={"X-Emberline-Mint": "test-mint"},
    )
    key = minted.json()["desk_key"]
    redeemed = client.post("/api/auth/redeem", json={"desk_key": key})
    token = redeemed.json()["access_token"]
    ws_id = redeemed.json()["user"]["workspace"]["id"]
    workspace = db.get(Workspace, ws_id)
    assert workspace is not None
    workspace.plan_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    blocked = client.post(
        "/api/watches",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "After expiry",
            "west": -122.5,
            "south": 37.0,
            "east": -121.5,
            "north": 38.0,
        },
    )
    assert blocked.status_code == 402
    usage = client.get("/api/billing/usage", headers={"Authorization": f"Bearer {token}"}).json()
    assert usage["plan_expired"] is True
    assert usage["plan_meta"]["runs"] == 0


# --- late payments -------------------------------------------------------
# A transfer that lands after the quote lapses used to be dropped, which turned
# a slow wallet into a manual refund. It now settles inside the grace window.

USDC_LIVE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def _age_invoice(db, invoice: BaseInvoice, *, minutes_past_due: int) -> BaseInvoice:
    """Push an invoice into the past so it is already lapsed."""
    invoice.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_past_due + 45)
    invoice.expires_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_past_due)
    db.commit()
    db.refresh(invoice)
    return invoice


def test_late_transfer_inside_the_grace_still_settles(client, db) -> None:
    from app.basepay import expire_stale, scan_payments
    from app.payfixture import get_fixture_rpc

    created = client.post("/api/public/pay/orders", json={"plan": "solo"}).json()
    invoice = db.get(BaseInvoice, created["id"])
    _age_invoice(db, invoice, minutes_past_due=90)
    expire_stale(db)
    db.commit()
    db.refresh(invoice)
    assert invoice.status == "expired"

    rpc = get_fixture_rpc()
    rpc.inject_usdc_transfer(token=USDC_LIVE, pay_to=invoice.pay_to, amount_raw=invoice.amount_raw)
    assert scan_payments(db, rpc=rpc) == 1

    db.refresh(invoice)
    assert invoice.status == "paid"
    assert invoice.desk_key and invoice.desk_key.startswith("emb_")

    view = client.get(f"/api/public/pay/invoices/{invoice.id}").json()
    assert view["status"] == "paid"
    assert view["late"] is True
    assert view["desk_key"] == invoice.desk_key


def test_a_transfer_past_the_grace_is_not_taken(client, db) -> None:
    from app.basepay import expire_stale, scan_payments
    from app.config import get_settings
    from app.payfixture import get_fixture_rpc

    grace = get_settings().pay_late_grace_hours
    created = client.post("/api/public/pay/orders", json={"plan": "solo"}).json()
    invoice = db.get(BaseInvoice, created["id"])
    _age_invoice(db, invoice, minutes_past_due=grace * 60 + 60)
    expire_stale(db)
    db.commit()

    rpc = get_fixture_rpc()
    rpc.inject_usdc_transfer(token=USDC_LIVE, pay_to=invoice.pay_to, amount_raw=invoice.amount_raw)
    assert scan_payments(db, rpc=rpc) == 0

    db.refresh(invoice)
    assert invoice.status == "expired"
    assert invoice.desk_key is None
    view = client.get(f"/api/public/pay/invoices/{invoice.id}").json()
    assert view["claimable"] is False


def test_an_invoice_in_grace_keeps_its_amount_reserved(client, db) -> None:
    from app.basepay import expire_stale

    first = client.post("/api/public/pay/orders", json={"plan": "solo"}).json()
    invoice = db.get(BaseInvoice, first["id"])
    _age_invoice(db, invoice, minutes_past_due=30)
    expire_stale(db)
    db.commit()

    response = client.post("/api/public/pay/orders", json={"plan": "solo"})
    assert response.status_code == 200, response.text
    second = response.json()
    assert second["amount_raw"] != first["amount_raw"]
    assert client.get(f"/api/public/pay/invoices/{first['id']}").json()["claimable"] is True


def test_confirm_refuses_a_transfer_older_than_the_invoice(db) -> None:
    invoice = BaseInvoice(
        id=new_id("inv"),
        plan="team",
        days=30,
        amount_raw=149_000091,
        status="pending",
        pay_to=TREASURY,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(invoice)
    db.commit()
    tx = "0x" + "22" * 32
    receipt = {
        "status": "0x1",
        "blockNumber": hex(50),
        "logs": [
            {
                "address": USDC,
                "topics": [TRANSFER, "0x" + "aa" * 32, topic_address(TREASURY)],
                "data": hex(149_000091),
                "transactionHash": tx,
                "blockNumber": hex(50),
                "logIndex": "0x0",
            }
        ],
    }
    stale = _FakeRpc(receipt, head=60, block_time=datetime.now(timezone.utc) - timedelta(days=2))
    try:
        confirm_invoice(db, invoice, tx, rpc=stale)
        raise AssertionError("expected a predates error")
    except ValueError as exc:
        assert "predates" in str(exc)
    db.refresh(invoice)
    assert invoice.status == "pending"
    assert invoice.desk_key is None


def test_confirm_accepts_a_late_transfer_but_not_one_past_the_grace(db) -> None:
    from app.config import get_settings

    grace = get_settings().pay_late_grace_hours
    now = datetime.now(timezone.utc)
    invoice = BaseInvoice(
        id=new_id("inv"),
        plan="team",
        days=30,
        amount_raw=149_000092,
        status="pending",
        pay_to=TREASURY,
        created_at=now - timedelta(hours=3),
        expires_at=now - timedelta(hours=2),
    )
    db.add(invoice)
    db.commit()
    tx = "0x" + "33" * 32
    receipt = {
        "status": "0x1",
        "blockNumber": hex(50),
        "logs": [
            {
                "address": USDC,
                "topics": [TRANSFER, "0x" + "aa" * 32, topic_address(TREASURY)],
                "data": hex(149_000092),
                "transactionHash": tx,
                "blockNumber": hex(50),
                "logIndex": "0x0",
            }
        ],
    }
    too_late = _FakeRpc(receipt, head=60, block_time=now + timedelta(hours=grace + 1))
    try:
        confirm_invoice(db, invoice, tx, rpc=too_late)
        raise AssertionError("expected a grace-window error")
    except ValueError as exc:
        assert "grace window" in str(exc)

    paid = confirm_invoice(db, invoice, tx, rpc=_FakeRpc(receipt, head=60, block_time=now - timedelta(hours=1)))
    assert paid.status == "paid"
    assert paid.desk_key.startswith("emb_")


def test_health_answers_whether_this_desk_can_sell_unattended(client) -> None:
    """The one line a deploy check reads. Same keys as the sibling desks, deliberately."""
    from app.basepay import PAY_SCAN_INTERVAL_SECONDS

    checkout = client.get("/api/public/health").json()["checkout"]
    assert set(checkout) == {"open", "reason", "settlement", "scan_interval_seconds", "last_scan"}
    assert checkout["open"] is True and checkout["reason"] == ""
    assert checkout["settlement"] in ("scheduled", "off")
    assert checkout["scan_interval_seconds"] == PAY_SCAN_INTERVAL_SECONDS
    assert set(checkout["last_scan"]) == {"at", "age_seconds", "chain_head", "settled_total"}


def test_health_shows_that_the_poll_actually_ran(client, db) -> None:
    """A scan that settles nothing logs nothing, so "open" alone proves nothing ran."""
    from app.basepay import scan_payments
    from app.payfixture import get_fixture_rpc

    created = client.post("/api/public/pay/orders", json={"plan": "solo"}).json()
    invoice = db.get(BaseInvoice, created["id"])
    rpc = get_fixture_rpc()
    rpc.inject_usdc_transfer(token=USDC_LIVE, pay_to=invoice.pay_to, amount_raw=invoice.amount_raw)
    assert scan_payments(db, rpc=rpc) == 1

    scan = client.get("/api/public/health").json()["checkout"]["last_scan"]
    assert scan["at"] and scan["age_seconds"] is not None
    assert scan["age_seconds"] < 60
    assert scan["chain_head"] and scan["settled_total"] >= 1


def test_rail_advertises_the_grace(client) -> None:
    rail = client.get("/api/public/pay/status").json()
    assert rail["late_grace_hours"] >= 1


def test_demo_mode_closes_checkout_even_when_fixture_would_quote(monkeypatch) -> None:
    from app.config import get_settings
    from app.main import create_app
    from desk_kernel.demo import DEMO_CHECKOUT_CLOSED

    monkeypatch.setenv("DESK_MODE", "demo")
    get_settings.cache_clear()
    with TestClient(create_app()) as demo_client:
        health = demo_client.get("/api/public/health").json()
        assert health["demo"] is True
        assert health["checkout"]["open"] is False
        assert "demo mode" in health["checkout"]["reason"]
        rail = demo_client.get("/api/public/pay/status").json()
        assert rail["enabled"] is False
        assert DEMO_CHECKOUT_CLOSED in rail["closed_reason"]
        assert demo_client.post("/api/public/pay/invoices", json={"plan": "solo"}).status_code == 503
        assert demo_client.get("/api/public/sample-brief").status_code == 200
    monkeypatch.setenv("DESK_MODE", "live")
    get_settings.cache_clear()


def test_live_fixture_rail_stays_open_when_desk_mode_is_live() -> None:
    from app.basepay import rail_closed_reason, rail_enabled
    from app.config import Settings

    settings = Settings.model_construct(
        desk_mode="live",
        pay_mode="fixture",
        app_env="development",
        pay_base_address=TREASURY,
    )
    assert rail_enabled(settings) is True
    assert rail_closed_reason(settings) == ""


def test_demo_closes_a_configured_live_rail() -> None:
    from app.basepay import rail_closed_reason, rail_enabled
    from app.config import Settings
    from desk_kernel.demo import DEMO_CHECKOUT_CLOSED

    settings = Settings.model_construct(
        desk_mode="demo",
        pay_mode="live",
        app_env="development",
        pay_base_address=LIVE_TREASURY,
        pay_base_rpc_url="https://example.invalid",
    )
    assert rail_enabled(settings) is False
    assert rail_closed_reason(settings) == DEMO_CHECKOUT_CLOSED
