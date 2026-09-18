"""A desk that cannot buy evidence must say so — to the operator, not to the customer.

Measured on the deployed desks 2026-09-12: the Hub answered 402 with its own price list,
free-allowance counters and "open a payment channel" instructions, and the desk handed that
text straight to a paying customer as the reason their run failed.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DESK_ID", "tideline")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")  # the per-test file DB is set in the fixture
os.environ.setdefault("JWT_SECRET", "test-secret-for-supply-failures")
os.environ.setdefault("SEED_DEMO", "true")
os.environ.setdefault("HUB_MODE", "fixture")
os.environ.setdefault("DESK_MODE", "live")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import desk_kernel.service.engine as engine_mod  # noqa: E402
from desk_kernel.hub import HubError  # noqa: E402
from desk_kernel.service.config import current_claim  # noqa: E402
from desk_kernel.service.db import Base, SessionLocal, engine  # noqa: E402
from desk_kernel.service.main import create_app  # noqa: E402
from desk_kernel.service.models import Run, Watch  # noqa: E402
from desk_kernel.service.seed import seed_demo  # noqa: E402
from desk_kernel.supply import failure_summary  # noqa: E402

HUB_402 = (
    'hub 402: {"detail":{"error":"payment_required","capability_id":"atlas.watchbox.check@v1",'
    '"price_per_call_usd":0.02,"free_allowance":{"max":5,"used":5},'
    '"how_to_continue":["Open a payment channel at the hub"]}}'
)


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "supply.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()
    with TestClient(create_app()) as c:
        yield c


def _token(client: TestClient) -> str:
    claim = current_claim()
    body = {"email": claim.demo_email, "password": claim.demo_password}
    return client.post("/api/auth/login", json=body).json()["access_token"]


def test_a_customer_is_not_shown_the_desks_supplier_terms(client: TestClient, monkeypatch) -> None:
    def refuse(*_args, **_kwargs):
        raise HubError(HUB_402)

    monkeypatch.setattr(engine_mod.HubClient, "invoke", refuse)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    watch = client.post(
        "/api/watches",
        headers=headers,
        json={"name": "Unpayable", "west": -1.0, "south": 51.3, "east": 0.2, "north": 51.6},
    ).json()
    body = client.post(f"/api/watches/{watch['id']}/run", headers=headers).json()

    assert body["status"] == "failed"
    assert body["failure"] == "supply_unpaid"
    for leak in ("price_per_call_usd", "free_allowance", "payment channel", "402"):
        assert leak not in body["error"], f"the desk leaked its supplier terms: {leak}"
    assert "Nothing was charged to your plan" in body["error"]

    # The operator still gets the whole thing, in the row and in health.
    db = SessionLocal()
    try:
        run = db.get(Run, body["id"])
        assert run is not None and "price_per_call_usd" in run.error
    finally:
        db.close()
    failure = client.get("/api/public/health").json()["supply"]["last_failure"]
    assert failure["kind"] == "supply_unpaid"
    assert "payment_required" in failure["detail"]
    assert failure["age_seconds"] is not None and failure["age_seconds"] < 60


def test_a_failed_run_does_not_eat_the_paid_quota(client: TestClient, monkeypatch) -> None:
    """The desk's own supply problem must not spend what the customer bought."""
    monkeypatch.setattr(
        engine_mod.HubClient, "invoke", lambda *_a, **_k: (_ for _ in ()).throw(HubError(HUB_402))
    )
    headers = {"Authorization": f"Bearer {_token(client)}"}
    watch = client.post(
        "/api/watches",
        headers=headers,
        json={"name": "Quota keeper", "west": -1.0, "south": 51.3, "east": 0.2, "north": 51.6},
    ).json()
    before = client.get("/api/billing/usage", headers=headers).json()["runs"]
    for _ in range(3):
        assert client.post(f"/api/watches/{watch['id']}/run", headers=headers).json()["status"] == "failed"
    after = client.get("/api/billing/usage", headers=headers).json()["runs"]
    assert after == before, "failed runs must not count against a paid plan"

    db = SessionLocal()
    try:
        assert db.query(Watch).filter(Watch.id == watch["id"]).one().status == "active"
    finally:
        db.close()


def test_the_operator_sees_the_balance_falling_before_it_runs_out(client: TestClient) -> None:
    """`supply_unpaid` above is too late: by then a customer's run has already failed.

    Driven through a real `httpx` response so the header names are checked against the
    upstream's wire format rather than against a hand-built dict.
    """
    import httpx

    from desk_kernel.supply import note_supply_credit

    note_supply_credit(
        httpx.Response(
            200,
            headers={
                "X-Atlas-Credit-Balance-Usd": "0.640000",
                "X-Atlas-Credit-Charged-Usd": "0.020000",
                "X-Atlas-Credit-Low": "1",
            },
        ).headers,
        seller="https://atlas.modelmarket.dev",
    )

    credit = client.get("/api/public/health").json()["supply"]["credit"]
    assert credit["seller"] == "https://atlas.modelmarket.dev", "whose balance is this?"
    assert credit["balance_usd"] == 0.64
    assert credit["charged_usd"] == 0.02
    assert credit["low"] is True
    assert credit["age_seconds"] is not None and credit["age_seconds"] < 60


def test_a_desk_buying_on_the_free_tier_reports_no_balance(client: TestClient) -> None:
    """Absent headers must read as "unknown", never as a balance of zero."""
    import desk_kernel.supply as supply_mod
    from desk_kernel.supply import note_supply_credit

    # Process state, shared with the test above: this one is about a desk that has never
    # been charged, so it starts from the state a fresh process would have.
    supply_mod._supply_credit.update(
        at=None, seller="", balance_usd=None, charged_usd=None, low=False
    )

    note_supply_credit({"content-type": "application/json"})
    note_supply_credit({"x-atlas-credit-balance-usd": "not-a-number"})
    note_supply_credit(None)

    credit = client.get("/api/public/health").json()["supply"]["credit"]
    assert credit["balance_usd"] is None and credit["at"] is None and credit["low"] is False


def test_an_unclassified_failure_still_says_nothing_was_charged() -> None:
    assert failure_summary("boom")["kind"] == "run_failed"
    assert "Nothing was charged" in failure_summary("boom")["message"]
    assert failure_summary(None) == {"kind": "", "message": ""}
    assert failure_summary("hub unreachable: timeout")["kind"] == "supply_unreachable"
    assert failure_summary("hub 429: slow down")["kind"] == "supply_throttled"
