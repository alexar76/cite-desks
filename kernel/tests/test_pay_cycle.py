"""Checkout must complete with nobody in the loop, and refuse rather than half-complete.

Every desk on the kernel sells the same way: a unique USDC micro-amount is quoted, the
buyer's wallet pays it, a scheduled scan of the treasury turns that transfer into a desk
key, and the key provisions a workspace. No step waits for a person. These tests hold that
line from both directions — the happy path settles unattended, and the ways a desk could
take money it cannot honour (or hand a key to the wrong buyer) all fail closed.
"""

from __future__ import annotations

import os
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

from desk_kernel import chain
from desk_kernel.service import pay
from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.service.db import Base, SessionLocal, engine
from desk_kernel.service.main import create_app
from desk_kernel.service.models import BaseInvoice, DeskGrant
from desk_kernel.service.payfixture import get_fixture_rpc, reset_fixture_rpc
from desk_kernel.service.security import reset_rate_limits
from desk_kernel.service.seed import seed_demo

LIVE_TREASURY = "0x" + "de" * 20


def _reset(desk_id: str = "tideline", *, pay_mode: str = "fixture", treasury: str = "", desk_mode: str = "live") -> None:
    os.environ["DESK_ID"] = desk_id
    os.environ["PAY_MODE"] = pay_mode
    os.environ["PAY_BASE_ADDRESS"] = treasury
    os.environ["DESK_MODE"] = desk_mode
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


@pytest.fixture()
def client():
    _reset()
    with TestClient(create_app("tideline")) as test_client:
        yield test_client
    _reset()


@pytest.fixture()
def live_client():
    """A desk configured exactly like production: PAY_MODE=live, a real treasury."""
    _reset(pay_mode="live", treasury=LIVE_TREASURY)
    with TestClient(create_app("tideline")) as test_client:
        yield test_client
    _reset()


def _pay_on_chain(rpc, invoice_row: dict, *, amount_raw: int | None = None) -> str:
    """What a buyer's wallet does: one USDC transfer to the quoted address."""
    transfer = rpc.inject_usdc_transfer(
        token=get_settings().pay_usdc_address,
        pay_to=invoice_row["pay_to"],
        amount_raw=amount_raw if amount_raw is not None else int(invoice_row["amount_raw"]),
    )
    return transfer.tx_hash


def _scan(rpc=None) -> int:
    db = SessionLocal()
    try:
        return pay.scan_payments(db, rpc=rpc)
    finally:
        db.close()


# --------------------------------------------------------------- the unattended happy path


def test_quote_to_working_desk_without_a_human(client: TestClient) -> None:
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    assert invoice["status"] == "pending"
    assert invoice["eip681"].startswith("ethereum:")
    assert invoice["desk_key"] is None

    _pay_on_chain(get_fixture_rpc(), invoice)
    assert _scan(get_fixture_rpc()) == 1, "the scheduled scan must settle a paid invoice"

    # The buyer's browser polls; nobody looks in the database for them.
    settled = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()
    assert settled["status"] == "paid"
    assert settled["tx_hash"]
    key = settled["desk_key"]
    assert key and key.startswith(current_claim().key_prefix)

    redeemed = client.post("/api/auth/redeem", json={"desk_key": key})
    assert redeemed.status_code == 200
    body = redeemed.json()
    assert body["user"]["workspace"]["plan"] == "solo"
    assert body["user"]["workspace"]["plan_expires_at"]

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    watch = client.post(
        "/api/watches",
        headers=headers,
        json={"name": "Bought basin", "west": -1.0, "south": 51.3, "east": 0.2, "north": 51.6},
    )
    assert watch.status_code == 200
    run = client.post(f"/api/watches/{watch.json()['id']}/run", headers=headers)
    assert run.status_code == 200 and run.json()["status"] == "completed"


def test_health_shows_that_the_poll_actually_ran(client: TestClient) -> None:
    """"open": true only says the desk intends to settle. This says a scan happened.

    A scan that settles nothing logs nothing, so a stopped scheduler and a quiet treasury
    are indistinguishable from outside — until a buyer's USDC sits unsettled.
    """
    before = client.get("/api/public/health").json()["checkout"]["last_scan"]
    assert set(before) == {"at", "age_seconds", "chain_head", "settled_total"}

    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice)
    assert _scan(get_fixture_rpc()) == 1

    after = client.get("/api/public/health").json()["checkout"]["last_scan"]
    assert after["at"] and after["age_seconds"] is not None and after["age_seconds"] < 60
    assert after["chain_head"] and after["settled_total"] >= 1


def test_paid_window_starts_when_the_money_landed(client: TestClient) -> None:
    invoice = client.post("/api/public/pay/invoices", json={"plan": "team"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice)
    _scan(get_fixture_rpc())
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    workspace = client.post("/api/auth/redeem", json={"desk_key": key}).json()["user"]["workspace"]
    assert workspace["plan"] == "team"
    ends = datetime.fromisoformat(workspace["plan_expires_at"])
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    # 30 paid days from settlement, not from whenever the key was pasted.
    assert timedelta(days=29) < ends - datetime.now(timezone.utc) < timedelta(days=31)


def test_the_key_stops_being_readable_once_redeemed(client: TestClient) -> None:
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice)
    _scan(get_fixture_rpc())
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    client.post("/api/auth/redeem", json={"desk_key": key})
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"] is None


def test_redeeming_twice_is_the_same_desk(client: TestClient) -> None:
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice)
    _scan(get_fixture_rpc())
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    first = client.post("/api/auth/redeem", json={"desk_key": key}).json()
    second = client.post("/api/auth/redeem", json={"desk_key": key}).json()
    assert first["user"]["workspace"]["id"] == second["user"]["workspace"]["id"]


# ------------------------------------------------------------------ live mode, no fixtures


def test_live_mode_settles_from_treasury_logs(live_client: TestClient) -> None:
    """The live rail is not merely unblocked — a real chain log buys a real key.

    This is the case the kernel used to refuse outright: PAY_MODE=live had no watcher, so
    every sibling desk quoted nothing in production. The RPC here is a stub, but the code
    path is the production one: fetch_transfers → match_invoice → settle.
    """
    settings = get_settings()
    assert not pay.fixture_allowed(settings)
    rail = live_client.get("/api/public/pay/status").json()
    assert rail["enabled"] and not rail["fixture"] and rail["pay_to"] == LIVE_TREASURY

    invoice = live_client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    assert invoice["pay_to"] == LIVE_TREASURY

    from desk_kernel.service.payfixture import FixtureRpc

    rpc = FixtureRpc()
    _pay_on_chain(rpc, invoice)
    assert _scan(rpc) == 1

    settled = live_client.get(f"/api/public/pay/invoices/{invoice['id']}").json()
    assert settled["status"] == "paid"
    assert live_client.post("/api/auth/redeem", json={"desk_key": settled["desk_key"]}).status_code == 200


def test_demo_settlement_route_is_absent_in_live_mode(live_client: TestClient) -> None:
    invoice = live_client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    for route in ("fixture", "simulate"):
        assert live_client.post(f"/api/public/pay/invoices/{invoice['id']}/{route}").status_code == 404


def test_confirm_settles_without_waiting_for_the_next_poll(live_client: TestClient) -> None:
    from desk_kernel.service.payfixture import FixtureRpc

    rpc = FixtureRpc()
    invoice = live_client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    tx = _pay_on_chain(rpc, invoice)
    db = SessionLocal()
    try:
        row = db.get(BaseInvoice, invoice["id"])
        settled = pay.confirm_invoice(db, row, tx, rpc=rpc)
        assert settled.status == "paid" and settled.desk_key
    finally:
        db.close()


# --------------------------------------------------------------------- fails closed instead


def test_live_mode_without_a_treasury_closes_checkout() -> None:
    """No address means no quote. The alternative is USDC sent to an address nobody owns."""
    _reset(pay_mode="live", treasury="")
    with TestClient(create_app("tideline")) as client:
        health = client.get("/api/public/health").json()
        assert health["checkout"]["open"] is False
        assert "PAY_BASE_ADDRESS" in health["checkout"]["reason"]
        rail = client.get("/api/public/pay/status").json()
        assert rail["enabled"] is False and rail["closed_reason"]
        refused = client.post("/api/public/pay/invoices", json={"plan": "solo"})
        assert refused.status_code == 503
    _reset()


def test_live_mode_refuses_the_placeholder_treasury() -> None:
    """0x1111… is the fixture treasury. In live mode it is somebody else's wallet."""
    _reset(pay_mode="live", treasury="0x1111111111111111111111111111111111111111")
    with TestClient(create_app("tideline")) as client:
        assert client.post("/api/public/pay/invoices", json={"plan": "solo"}).status_code == 503
        assert "placeholder" in client.get("/api/public/pay/status").json()["closed_reason"]
    _reset()


def test_scan_ignores_a_transfer_that_pays_a_different_amount(client: TestClient) -> None:
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice, amount_raw=int(invoice["amount_raw"]) + 7)
    assert _scan(get_fixture_rpc()) == 0
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["status"] == "pending"


def test_one_transfer_buys_exactly_one_key(client: TestClient) -> None:
    """A rescan sees the same log again. It must not mint a second grant."""
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice)
    assert _scan(get_fixture_rpc()) == 1
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    assert _scan(get_fixture_rpc()) == 0
    assert client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"] == key
    db = SessionLocal()
    try:
        assert db.query(DeskGrant).count() == 1
    finally:
        db.close()


def test_a_second_invoice_cannot_claim_a_spent_transfer(client: TestClient) -> None:
    """The tx hash is the receipt. Reusing it on a fresh quote must be refused."""
    rpc = get_fixture_rpc()
    first = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    tx = _pay_on_chain(rpc, first)
    _scan(rpc)
    second = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    replayed = client.post(f"/api/public/pay/invoices/{second['id']}/confirm", json={"tx_hash": tx})
    assert replayed.status_code == 409
    db = SessionLocal()
    try:
        assert db.get(BaseInvoice, second["id"]).desk_key is None
    finally:
        db.close()


def test_confirm_refuses_a_transfer_older_than_the_invoice(live_client: TestClient) -> None:
    """Otherwise the grace window becomes a way to claim somebody's stray payment."""
    from desk_kernel.service.payfixture import FixtureRpc

    rpc = FixtureRpc()
    invoice = live_client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    stale = rpc.inject_usdc_transfer(
        token=get_settings().pay_usdc_address,
        pay_to=invoice["pay_to"],
        amount_raw=int(invoice["amount_raw"]),
        timestamp=int((datetime.now(timezone.utc) - timedelta(hours=6)).timestamp()),
    )
    db = SessionLocal()
    try:
        row = db.get(BaseInvoice, invoice["id"])
        with pytest.raises(ValueError, match="predates"):
            pay.confirm_invoice(db, row, stale.tx_hash, rpc=rpc)
    finally:
        db.close()


def test_confirm_waits_for_the_confirmation_depth(live_client: TestClient) -> None:
    from desk_kernel.service.payfixture import FixtureRpc

    rpc = FixtureRpc()
    invoice = live_client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    tx = _pay_on_chain(rpc, invoice)
    rpc.head -= 2                      # roll the head back under PAY_BASE_CONFIRMATIONS
    db = SessionLocal()
    try:
        row = db.get(BaseInvoice, invoice["id"])
        with pytest.raises(ValueError, match="confirmations"):
            pay.confirm_invoice(db, row, tx, rpc=rpc)
    finally:
        db.close()


# ----------------------------------------------------------------- amounts, TTL, and grace


def test_amounts_stay_unique_while_an_invoice_can_still_be_paid(client: TestClient) -> None:
    amounts = {
        client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()["amount_raw"]
        for _ in range(5)
    }
    assert len(amounts) == 5


def test_a_lapsed_quote_keeps_its_amount_through_the_grace_window(client: TestClient) -> None:
    """An expired invoice is still payable, so its amount is not free to hand out again."""
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    db = SessionLocal()
    try:
        row = db.get(BaseInvoice, invoice["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()
        pay.expire_stale(db)
        db.commit()
        assert db.get(BaseInvoice, invoice["id"]).status == "expired"
    finally:
        db.close()
    reissued = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    assert reissued["amount_raw"] != invoice["amount_raw"]
    # ...and a slow wallet paying the old amount inside the grace still gets its key.
    _pay_on_chain(get_fixture_rpc(), invoice)
    assert _scan(get_fixture_rpc()) == 1
    late = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()
    assert late["status"] == "paid" and late["late"] is True and late["desk_key"]


def test_a_transfer_after_the_grace_window_does_not_settle(client: TestClient) -> None:
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    db = SessionLocal()
    try:
        row = db.get(BaseInvoice, invoice["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(
            seconds=pay.grace_seconds() + 3600
        )
        row.status = "expired"
        db.commit()
    finally:
        db.close()
    _pay_on_chain(get_fixture_rpc(), invoice)
    assert _scan(get_fixture_rpc()) == 0


def test_an_unknown_or_expired_key_buys_nothing(client: TestClient) -> None:
    assert client.post("/api/auth/redeem", json={"desk_key": "tdl_nothing_at_all"}).status_code == 401
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice)
    _scan(get_fixture_rpc())
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    db = SessionLocal()
    try:
        grant = db.query(DeskGrant).one()
        grant.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    finally:
        db.close()
    assert client.post("/api/auth/redeem", json={"desk_key": key}).status_code == 410


def test_an_expired_plan_stops_buying_hub_runs(client: TestClient) -> None:
    """The paid window is enforced on the way out, not only sold on the way in."""
    invoice = client.post("/api/public/pay/invoices", json={"plan": "solo"}).json()
    _pay_on_chain(get_fixture_rpc(), invoice)
    _scan(get_fixture_rpc())
    key = client.get(f"/api/public/pay/invoices/{invoice['id']}").json()["desk_key"]
    session = client.post("/api/auth/redeem", json={"desk_key": key}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    watch = client.post(
        "/api/watches",
        headers=headers,
        json={"name": "Basin", "west": -1.0, "south": 51.3, "east": 0.2, "north": 51.6},
    ).json()
    from desk_kernel.service.models import Workspace

    db = SessionLocal()
    try:
        workspace = db.get(Workspace, session["user"]["workspace"]["id"])
        workspace.plan_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    finally:
        db.close()
    assert client.post(f"/api/watches/{watch['id']}/run", headers=headers).status_code == 402


# ------------------------------------------------------------------- the scanner's log walk


class NarrowWindowRpc:
    """An endpoint like 1rpc: serves 50 blocks and refuses anything wider."""

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit
        self.windows: list[tuple[int, int]] = []
        self.refusals = 0

    def call(self, method, params):
        if method == "eth_blockNumber":
            return hex(1_000_000)
        if method != "eth_getLogs":
            raise AssertionError(method)
        lo = int(params[0]["fromBlock"], 16)
        hi = int(params[0]["toBlock"], 16)
        if hi - lo + 1 > self.limit:
            self.refusals += 1
            raise chain.RpcError(f"https://1rpc.io/base: eth_getLogs is limited to 0 - {self.limit} blocks range")
        self.windows.append((lo, hi))
        return []


def _cfg() -> chain.ChainConfig:
    return chain.ChainConfig(
        token=get_settings().pay_usdc_address,
        pay_to=LIVE_TREASURY,
        chain_id=8453,
        confirmations=2,
        rpc_urls=("https://example.invalid",),
    )


def test_a_narrow_endpoint_still_gets_the_whole_range_scanned() -> None:
    rpc = NarrowWindowRpc(limit=50)
    assert chain.fetch_transfers(rpc, _cfg(), from_block=1_000, to_block=1_499) == []
    assert rpc.refusals > 0, "the fixture never exercised the refusal path"
    covered: set[int] = set()
    for lo, hi in rpc.windows:
        assert hi - lo + 1 <= 50
        for block in range(lo, hi + 1):
            assert block not in covered, f"block {block} scanned twice"
            covered.add(block)
    assert covered == set(range(1_000, 1_500)), "the scan left a hole in the range"


def test_a_wide_endpoint_is_not_punished_with_tiny_windows() -> None:
    rpc = NarrowWindowRpc(limit=10_000)
    chain.fetch_transfers(rpc, _cfg(), from_block=0, to_block=chain.LOG_WINDOW_BLOCKS - 1)
    assert rpc.refusals == 0
    assert rpc.windows == [(0, chain.LOG_WINDOW_BLOCKS - 1)]


def test_a_non_range_error_is_not_silently_absorbed() -> None:
    """Only 'ask for less' is recoverable. Anything else must reach the caller."""

    class Broken:
        def call(self, method, params):
            if method == "eth_blockNumber":
                return hex(10)
            raise chain.RpcError("https://x: 401 Client Error: Unauthorized")

    with pytest.raises(chain.RpcError):
        chain.fetch_transfers(Broken(), _cfg(), from_block=0, to_block=10)


def test_transfers_to_another_address_are_not_ours() -> None:
    logs = [
        {
            "address": get_settings().pay_usdc_address,
            "topics": [
                chain.TRANSFER_TOPIC,
                chain.topic_address("0x" + "bb" * 20),
                chain.topic_address("0x" + "cc" * 20),
            ],
            "data": hex(49_000_001),
            "transactionHash": "0x" + "de" * 32,
            "blockNumber": "0x1",
            "logIndex": "0x0",
        }
    ]
    assert chain.parse_transfer_logs(logs, token=get_settings().pay_usdc_address, pay_to=LIVE_TREASURY) == []


def test_an_endpoint_list_survives_however_the_operator_separated_it() -> None:
    """Commas, semicolons, whitespace and newlines all mean "another endpoint".

    A separator the parser does not know does not fail loudly: the pair survives as one
    string that still starts with https://, so it is kept, tried, and fails every call —
    an RPC list one entry shorter than the operator believes.
    """
    urls = chain.parse_rpc_urls("https://a.example, https://b.example;https://c.example\nhttps://a.example/")
    assert urls == ["https://a.example", "https://b.example", "https://c.example"]
    full = chain.rpc_url_list("https://own.example/rpc;https://spare.example")
    assert full[:2] == ["https://own.example/rpc", "https://spare.example"]
    assert "https://mainnet.base.org" in full, "operator endpoints must not drop the backups"


# -------------------------------------------------------------------- production gate


def test_production_refuses_a_desk_that_cannot_settle() -> None:
    from desk_kernel.claim import TIDELINE
    from desk_kernel.service.config import Settings, assert_runtime_safety

    base = dict(
        desk_id="tideline",
        app_env="production",
        jwt_secret="not-the-default-secret-value-at-all",
        seed_demo=False,
        pay_mode="live",
        pay_mint_secret="mint",
        hub_mode="live",
        hub_api_key="k",
    )
    with pytest.raises(RuntimeError, match="PAY_BASE_ADDRESS is required"):
        assert_runtime_safety(Settings(**base, pay_base_address=""), TIDELINE)
    with pytest.raises(RuntimeError, match="real treasury"):
        assert_runtime_safety(
            Settings(**base, pay_base_address="0x1111111111111111111111111111111111111111"), TIDELINE
        )
    with pytest.raises(RuntimeError, match="valid Base address"):
        assert_runtime_safety(Settings(**base, pay_base_address="0xnope"), TIDELINE)
    assert_runtime_safety(Settings(**base, pay_base_address=LIVE_TREASURY), TIDELINE)


def test_every_desk_prefixes_its_own_keys_and_invoices() -> None:
    """Two desks must never issue a key or an invoice number the other could accept."""
    from desk_kernel.claim import CLAIMS

    prefixes = {claim.key_prefix for claim in CLAIMS.values()}
    numbers = {claim.invoice_prefix for claim in CLAIMS.values()}
    assert len(prefixes) == len(CLAIMS)
    assert len(numbers) == len(CLAIMS)
