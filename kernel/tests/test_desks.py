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
os.environ.setdefault("DESK_MODE", "live")
os.environ["DESK_ID"] = "tideline"

from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.service.db import Base, SessionLocal, engine
from desk_kernel.service.main import create_app
from desk_kernel.service.seed import seed_demo


def _client_for(desk_id: str) -> TestClient:
    os.environ["DESK_ID"] = desk_id
    get_settings.cache_clear()
    current_claim.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()
    return TestClient(create_app(desk_id))


def test_solrecord_point_run_and_citepack() -> None:
    with _client_for("solrecord") as client:
        health = client.get("/api/public/health").json()
        assert health["service"] == "solrecord"
        status = client.get("/api/public/status").json()
        assert status["watch_kind"] == "point"
        assert "yield forecast" in status["not"]
        sample = client.get("/api/public/sample-brief").json()
        assert sample["irradiance"]
        assert sample["record_kind"] == "retrospective_record_of_fact"
        token = client.post(
            "/api/auth/login",
            json={"email": "owner@solrecorddesk.com", "password": "solrecord-demo"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        watches = client.get("/api/watches", headers=headers).json()
        ran = client.post(f"/api/watches/{watches[0]['id']}/run", headers=headers)
        assert ran.status_code == 200
        pack = client.get(f"/api/briefs/{ran.json()['brief_id']}/cite-pack", headers=headers)
        assert pack.status_code == 200
        assert pack.headers["content-type"].startswith("application/zip")


def test_seamark_refuses_non_nordic_bbox() -> None:
    with _client_for("seamark") as client:
        status = client.get("/api/public/status").json()
        assert "global AIS" in status["not"]
        sample = client.get("/api/public/sample-brief").json()
        assert sample["finnish_ais"]
        assert sample["claim_split"].startswith("Fintraffic")
        token = client.post(
            "/api/auth/login",
            json={"email": "owner@seamarkdesk.com", "password": "seamark-demo"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        refused = client.post(
            "/api/watches",
            headers=headers,
            json={"name": "Channel", "west": -5.0, "south": 50.0, "east": 1.0, "north": 51.0},
        )
        assert refused.status_code == 400
        ok = client.post(
            "/api/watches",
            headers=headers,
            json={"name": "Oslo approaches", "west": 10.4, "south": 59.7, "east": 10.9, "north": 59.99},
        )
        assert ok.status_code == 200


def test_plinth_named_site_and_citepack() -> None:
    with _client_for("plinth") as client:
        health = client.get("/api/public/health").json()
        assert health["service"] == "plinth"
        status = client.get("/api/public/status").json()
        assert "BMS" in status["not"]
        assert status["watch_kind"] == "bbox"
        sample = client.get("/api/public/sample-brief").json()
        assert sample["weather"]
        assert sample["air"]
        assert "campus risk score" in sample["claim_split"]
        press = client.get("/api/public/press").json()
        assert press["product"].startswith("Plinth")
        robots = client.get("/api/public/robots.txt")
        assert robots.status_code == 200
        assert b"plinthdesk.com/sitemap.xml" in robots.content
        sitemap = client.get("/api/public/sitemap.xml")
        assert sitemap.status_code == 200
        assert b"/sample" in sitemap.content
        token = client.post(
            "/api/auth/login",
            json={"email": "owner@plinthdesk.com", "password": "plinth-demo"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        too_big = client.post(
            "/api/watches",
            headers=headers,
            json={"name": "Virginia", "west": -80.0, "south": 36.5, "east": -75.0, "north": 39.5},
        )
        assert too_big.status_code == 400
        ran = client.post("/api/watches/" + client.get("/api/watches", headers=headers).json()[0]["id"] + "/run", headers=headers)
        assert ran.status_code == 200
        pack = client.get(f"/api/briefs/{ran.json()['brief_id']}/cite-pack", headers=headers)
        assert pack.status_code == 200
        assert pack.headers["content-type"].startswith("application/zip")


def test_production_refuses_fixture_hub() -> None:
    from desk_kernel.claim import TIDELINE
    from desk_kernel.service.config import Settings, assert_runtime_safety

    with pytest.raises(RuntimeError, match="HUB_MODE"):
        assert_runtime_safety(
            Settings(
                desk_id="tideline",
                app_env="production",
                jwt_secret="not-the-default-secret-value-at-all",
                seed_demo=False,
                pay_mode="live",
                pay_mint_secret="mint",
                hub_mode="fixture",
                hub_api_key="k",
            ),
            TIDELINE,
        )


def test_production_accepts_complete_hub_channel_without_credit_key() -> None:
    from desk_kernel.claim import TIDELINE
    from desk_kernel.service.config import Settings, assert_runtime_safety

    assert_runtime_safety(
        Settings(
            desk_id="tideline",
            app_env="production",
            jwt_secret="not-the-default-secret-value-at-all",
            seed_demo=False,
            pay_mode="live",
            pay_mint_secret="mint",
            pay_base_address="0x2222222222222222222222222222222222222222",
            hub_mode="live",
            hub_payment_channel="channel-1",
            hub_payment_channel_secret="channel-secret",
        ),
        TIDELINE,
    )


def test_production_refuses_half_configured_hub_channel() -> None:
    from desk_kernel.claim import TIDELINE
    from desk_kernel.service.config import Settings, assert_runtime_safety

    with pytest.raises(RuntimeError, match="must be set together"):
        assert_runtime_safety(
            Settings(
                desk_id="tideline",
                app_env="production",
                jwt_secret="not-the-default-secret-value-at-all",
                seed_demo=False,
                pay_mode="live",
                pay_mint_secret="mint",
                pay_base_address="0x2222222222222222222222222222222222222222",
                hub_mode="live",
                hub_payment_channel="channel-1",
            ),
            TIDELINE,
        )
