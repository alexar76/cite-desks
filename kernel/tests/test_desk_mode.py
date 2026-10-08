"""DESK_MODE=demo closes checkout. DESK_MODE=live (default) still sells.

Fixture pay is not demo: it still quotes a USDC amount and mints a key. The public
reference host must set DESK_MODE=demo so nobody can pay us.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["HUB_MODE"] = "fixture"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO"] = "true"
os.environ["JWT_SECRET"] = "test-secret-must-be-at-least-32b"
os.environ["PAY_MODE"] = "fixture"
os.environ["DESK_ID"] = "tideline"
os.environ["DESK_MODE"] = "live"

from desk_kernel.claim import TIDELINE
from desk_kernel.demo import DEMO_CHECKOUT_CLOSED
from desk_kernel.service.config import Settings, assert_runtime_safety, current_claim, get_settings
from desk_kernel.service.db import Base, engine
from desk_kernel.service.main import create_app
from desk_kernel.service.pay import rail_closed_reason, rail_enabled
from desk_kernel.service.security import reset_rate_limits

LIVE_TREASURY = "0x" + "de" * 20


def _reset(*, desk_mode: str = "live", pay_mode: str = "fixture", treasury: str = "") -> None:
    os.environ["DESK_MODE"] = desk_mode
    os.environ["PAY_MODE"] = pay_mode
    os.environ["PAY_BASE_ADDRESS"] = treasury
    get_settings.cache_clear()
    current_claim.cache_clear()
    reset_rate_limits()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_demo_closes_checkout_even_when_fixture_pay_would_quote() -> None:
    """PAY_MODE=fixture still sells on an in-process chain. Demo must not."""
    _reset(desk_mode="demo", pay_mode="fixture")
    with TestClient(create_app("tideline")) as client:
        health = client.get("/api/public/health").json()
        assert health["demo"] is True
        assert health["desk_mode"] == "demo"
        assert health["checkout"]["open"] is False
        assert "demo mode" in health["checkout"]["reason"]
        status = client.get("/api/public/status").json()
        assert status["demo"] is True
        rail = client.get("/api/public/pay/status").json()
        assert rail["enabled"] is False
        assert DEMO_CHECKOUT_CLOSED in rail["closed_reason"]
        refused = client.post("/api/public/pay/invoices", json={"plan": "solo"})
        assert refused.status_code == 503
        sample = client.get("/api/public/sample-brief")
        assert sample.status_code == 200
    _reset()


def test_live_mode_with_fixture_pay_still_quotes() -> None:
    """Default DESK_MODE=live: development fixture checkout stays open."""
    _reset(desk_mode="live", pay_mode="fixture")
    with TestClient(create_app("tideline")) as client:
        health = client.get("/api/public/health").json()
        assert health["demo"] is False
        assert health["checkout"]["open"] is True
        created = client.post("/api/public/pay/invoices", json={"plan": "solo"})
        assert created.status_code == 200
        assert created.json()["status"] == "pending"
    _reset()


def test_live_mode_with_a_treasury_opens_the_usdc_rail() -> None:
    settings = Settings(
        desk_id="tideline",
        desk_mode="live",
        app_env="development",
        pay_mode="live",
        pay_base_address=LIVE_TREASURY,
        pay_base_rpc_url="https://example.invalid",
    )
    assert not settings.is_demo
    assert rail_enabled(settings) is True
    assert rail_closed_reason(settings) == ""


def test_demo_mode_closes_a_configured_live_rail() -> None:
    settings = Settings(
        desk_id="tideline",
        desk_mode="demo",
        app_env="development",
        pay_mode="live",
        pay_base_address=LIVE_TREASURY,
        pay_base_rpc_url="https://example.invalid",
    )
    assert settings.is_demo
    assert rail_enabled(settings) is False
    assert rail_closed_reason(settings) == DEMO_CHECKOUT_CLOSED


def test_demo_production_boots_without_a_treasury() -> None:
    assert_runtime_safety(
        Settings(
            desk_id="tideline",
            desk_mode="demo",
            app_env="production",
            jwt_secret="not-the-default-secret-value-at-all",
            seed_demo=True,
            pay_mode="fixture",
            hub_mode="fixture",
            pay_base_address="",
        ),
        TIDELINE,
    )


def test_merchant_production_still_requires_a_treasury() -> None:
    with pytest.raises(RuntimeError, match="PAY_BASE_ADDRESS is required"):
        assert_runtime_safety(
            Settings(
                desk_id="tideline",
                desk_mode="live",
                app_env="production",
                jwt_secret="not-the-default-secret-value-at-all",
                seed_demo=False,
                pay_mode="live",
                pay_mint_secret="mint",
                hub_mode="live",
                hub_api_key="k",
                pay_base_address="",
            ),
            TIDELINE,
        )
