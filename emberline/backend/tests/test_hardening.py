from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, assert_runtime_safety
from app.geo import in_quiet_hours, parse_cron_or_interval
from app.hub import HubClient, HubError
from app.webhooks import UnsafeWebhook, assert_safe_webhook_url


def test_production_rejects_default_jwt() -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_runtime_safety(
            Settings.model_construct(
                app_env="production",
                jwt_secret="emberline-dev-secret-change-me",
                seed_demo=False,
                database_url="postgresql://emberline:other@db/emberline",
            )
        )


def test_production_rejects_demo_seed() -> None:
    with pytest.raises(RuntimeError, match="SEED_DEMO"):
        assert_runtime_safety(
            Settings.model_construct(
                app_env="production",
                jwt_secret="not-the-default-secret-value",
                seed_demo=True,
                database_url="postgresql://emberline:other@db/emberline",
            )
        )


def test_blocks_private_webhooks() -> None:
    with pytest.raises(UnsafeWebhook):
        assert_safe_webhook_url("http://example.com/hook")
    with pytest.raises(UnsafeWebhook):
        assert_safe_webhook_url("https://127.0.0.1/hook")
    with pytest.raises(UnsafeWebhook):
        assert_safe_webhook_url("https://localhost/hook")
    with pytest.raises(UnsafeWebhook):
        assert_safe_webhook_url("https://169.254.169.254/latest/meta-data")


def test_live_hub_requires_key() -> None:
    client = HubClient(mode="live")
    client.api_key = ""
    client.payment_channel = ""
    client.payment_channel_secret = ""
    with pytest.raises(HubError, match="HUB_API_KEY"):
        client.invoke("atlas.fire.weather@v1", {"west": -122, "south": 36, "east": -121, "north": 38})


def test_live_hub_keeps_credit_key_at_central_hub(monkeypatch) -> None:
    class Response:
        status_code = 200
        text = ""
        headers: dict[str, str] = {}

        @staticmethod
        def json() -> dict:
            return {
                "result": {"ok": True},
                "receipt": {"nonce": "paid-call"},
                "price_usd": 0.004,
            }

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        @staticmethod
        def post(url, *, json, headers):
            assert url == "https://modelmarket.dev/ai-market/v2/invoke"
            assert json["product_id"] == "atlas.products"
            assert json["source_hub"] == "https://atlas.modelmarket.dev"
            assert headers["X-API-Key"] == "credit-key"
            assert "Authorization" not in headers
            return Response()

    monkeypatch.setattr("app.hub.httpx.Client", Client)
    client = HubClient(mode="live")
    client.base = "https://modelmarket.dev"
    client.api_key = "credit-key"
    client.payment_channel = ""
    client.payment_channel_secret = ""

    result = client.invoke("atlas.fire.weather@v1", {"west": -122})

    assert result["_hub_envelope"]["hub_url"] == "https://modelmarket.dev"
    assert result["_hub_envelope"]["source_hub"] == "https://atlas.modelmarket.dev"
    assert result["_hub_envelope"]["receipt"]["nonce"] == "paid-call"


def test_live_hub_payment_channel_wins_over_api_key(monkeypatch) -> None:
    class Response:
        status_code = 200
        text = ""
        headers: dict[str, str] = {}

        @staticmethod
        def json() -> dict:
            return {"ok": True}

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        @staticmethod
        def post(_url, *, json, headers):
            assert "source_hub" not in json
            assert headers["X-Payment-Channel"] == "channel-1"
            assert headers["X-Payment-Channel-Secret"] == "channel-secret"
            assert "X-API-Key" not in headers
            assert "Authorization" not in headers
            return Response()

    monkeypatch.setattr("app.hub.httpx.Client", Client)
    client = HubClient(mode="live")
    client.base = "https://atlas.modelmarket.dev"
    client.api_key = "credit-key"
    client.payment_channel = "channel-1"
    client.payment_channel_secret = "channel-secret"

    client.invoke("atlas.fire.weather@v1", {"west": -122})


def test_rejects_cron_schedule() -> None:
    with pytest.raises(ValueError):
        parse_cron_or_interval("cron:0 * * * *")


def test_quiet_hours_overnight() -> None:
    now = datetime(2026, 8, 16, 23, 0, tzinfo=timezone.utc)
    assert in_quiet_hours("22-06", "UTC", now)
    assert not in_quiet_hours("22-06", "UTC", datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc))


def test_mint_and_redeem(client: TestClient) -> None:
    denied = client.post("/api/pay/mint", json={"plan": "solo", "days": 30, "payment_ref": "inv_1"})
    assert denied.status_code == 401
    minted = client.post(
        "/api/pay/mint",
        json={"plan": "solo", "days": 30, "payment_ref": "inv_1"},
        headers={"X-Emberline-Mint": "test-mint"},
    )
    assert minted.status_code == 200
    key = minted.json()["desk_key"]
    assert key.startswith("emb_")
    replay = client.post(
        "/api/pay/mint",
        json={"plan": "solo", "days": 30, "payment_ref": "inv_1"},
        headers={"X-Emberline-Mint": "test-mint"},
    )
    assert replay.status_code == 409
    redeemed = client.post("/api/auth/redeem", json={"desk_key": key})
    assert redeemed.status_code == 200
    token = redeemed.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["workspace"]["plan"] == "solo"


def test_production_rejects_fixture_pay_and_dummy_treasury() -> None:
    with pytest.raises(RuntimeError, match="PAY_MODE"):
        assert_runtime_safety(
            Settings.model_construct(
                app_env="production",
                jwt_secret="not-the-default-secret-value-32b",
                seed_demo=False,
                database_url="postgresql://emberline:other@db/emberline",
                pay_mode="fixture",
                pay_mint_secret="mint",
                pay_base_rpc_url="https://example.invalid",
                pay_base_address="0x2222222222222222222222222222222222222222",
            )
        )
    with pytest.raises(RuntimeError, match="PAY_BASE_ADDRESS"):
        assert_runtime_safety(
            Settings.model_construct(
                app_env="production",
                jwt_secret="not-the-default-secret-value-32b",
                seed_demo=False,
                database_url="postgresql://emberline:other@db/emberline",
                pay_mode="live",
                pay_mint_secret="mint",
                pay_base_rpc_url="https://example.invalid",
                pay_base_address="0x1111111111111111111111111111111111111111",
            )
        )
    assert_runtime_safety(
        Settings.model_construct(
            app_env="production",
            jwt_secret="not-the-default-secret-value-32b",
            seed_demo=False,
            database_url="postgresql://emberline:other@db/emberline",
            pay_mode="live",
            pay_mint_secret="mint",
            pay_base_rpc_url="https://mainnet.base.org,https://1rpc.io/base",
            pay_base_address="",
            hub_mode="live",
            hub_api_key="hub-credit-key",
        )
    )


def test_production_rejects_fixture_hub() -> None:
    with pytest.raises(RuntimeError, match="HUB_MODE"):
        assert_runtime_safety(
            Settings.model_construct(
                app_env="production",
                jwt_secret="not-the-default-secret-value-32b",
                seed_demo=False,
                database_url="postgresql://emberline:other@db/emberline",
                pay_mode="live",
                pay_mint_secret="mint",
                pay_base_address="",
                hub_mode="fixture",
                hub_api_key="hub-credit-key",
            )
        )


def test_rejects_localhost_webhook_on_create(client: TestClient) -> None:
    token = client.post(
        "/api/auth/login",
        json={"email": "owner@emberlinedesk.com", "password": "emberline-demo"},
    ).json()["access_token"]
    response = client.post(
        "/api/watches",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Bad hook",
            "west": -122.5,
            "south": 37.0,
            "east": -121.5,
            "north": 38.0,
            "https_webhook": "https://127.0.0.1/hook",
        },
    )
    assert response.status_code == 422


def test_demo_production_boots_without_a_treasury() -> None:
    assert_runtime_safety(
        Settings(
            app_env="production",
            desk_mode="demo",
            jwt_secret="not-the-default-secret-value-32b",
            seed_demo=True,
            pay_mode="fixture",
            hub_mode="fixture",
            database_url="postgresql://emberline:other@db/emberline",
            pay_base_address="",
        )
    )

