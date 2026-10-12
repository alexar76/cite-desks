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
from desk_kernel.service.db import Base, engine
from desk_kernel.service.main import create_app
from desk_kernel.service.seed import seed_demo
from desk_kernel.service.db import SessionLocal


@pytest.fixture()
def client():
    os.environ["DESK_ID"] = "tideline"
    get_settings.cache_clear()
    current_claim.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()
    with TestClient(create_app("tideline")) as test_client:
        yield test_client


def test_tideline_health_and_split(client: TestClient) -> None:
    health = client.get("/api/public/health")
    assert health.status_code == 200
    assert health.json()["service"] == "tideline"
    status = client.get("/api/public/status")
    assert "flood model" in status.json()["not"]
    sample = client.get("/api/public/sample-brief").json()
    assert sample["warnings"]
    assert sample["gauges"]
    assert "NOT A FLOOD MODEL" in sample["badges"]


def test_tideline_i18n_guide(client: TestClient) -> None:
    dutch = client.get("/api/public/i18n?lang=nl")
    assert dutch.status_code == 200
    body = dutch.json()
    assert body["locale"] == "nl"
    assert body["ui"]["cta_guide"]
    assert any(sec["id"] == "host" for sec in body["guide"]["sections"])
    status = client.get("/api/public/status?lang=de").json()
    assert status["locale"] == "de"
    assert status["host_region"] == "nl"


def test_tideline_login_run_citepack(client: TestClient) -> None:
    login = client.post("/api/auth/login", json={"email": "owner@tidelinedesk.com", "password": "tideline-demo"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    watches = client.get("/api/watches", headers=headers).json()
    assert watches
    ran = client.post(f"/api/watches/{watches[0]['id']}/run", headers=headers)
    assert ran.status_code == 200
    assert ran.json()["status"] == "completed"
    brief_id = ran.json()["brief_id"]
    pack = client.get(f"/api/briefs/{brief_id}/cite-pack", headers=headers)
    assert pack.status_code == 200
    assert pack.headers["content-type"].startswith("application/zip")


def test_tideline_rejects_bad_bbox(client: TestClient) -> None:
    token = client.post("/api/auth/login", json={"email": "owner@tidelinedesk.com", "password": "tideline-demo"}).json()["access_token"]
    response = client.post(
        "/api/watches",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "bad", "west": 1, "south": 51, "east": -1, "north": 52},
    )
    assert response.status_code == 400


def test_tideline_share_and_salt_invoice(client: TestClient) -> None:
    from desk_kernel.service.seed import SAMPLE_SHARE_TOKEN

    shared = client.get(f"/api/public/briefs/{SAMPLE_SHARE_TOKEN}")
    assert shared.status_code == 200
    assert shared.headers.get("x-robots-tag", "").startswith("noindex")
    first = client.post("/api/public/pay/invoices", json={"plan": "solo"})
    second = client.post("/api/public/pay/invoices", json={"plan": "solo"})
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["amount_raw"] != second.json()["amount_raw"]
    assert first.json()["number"].startswith("TL-")
