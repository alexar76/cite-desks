from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Brief, Run
from app.seed import BRIEF_ID, DEMO_EMAIL, DEMO_PASSWORD, SAMPLE_SHARE_TOKEN, WATCH_ID


def _login(client: TestClient) -> str:
    response = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_a_customer_is_not_shown_the_desks_supplier_terms(client: TestClient, monkeypatch) -> None:
    """Measured on the deployed desks 2026-09-12: the Hub's 402 body — its price per call,
    its free-allowance counters, its "open a payment channel" advice — was handed to a
    paying customer as the reason their run failed."""
    from app import engine as engine_mod
    from app.hub import HubError

    raw = (
        'hub 402: {"detail":{"error":"payment_required","price_per_call_usd":0.02,'
        '"free_allowance":{"max":5,"used":5},"how_to_continue":["Open a payment channel"]}}'
    )
    monkeypatch.setattr(
        engine_mod.HubClient, "invoke", lambda *_a, **_k: (_ for _ in ()).throw(HubError(raw))
    )
    monkeypatch.setattr(
        engine_mod.HubClient, "fire_weather", lambda *_a, **_k: (_ for _ in ()).throw(HubError(raw))
    )
    token = _login(client)
    body = client.post(f"/api/watches/{WATCH_ID}/run", headers={"Authorization": f"Bearer {token}"}).json()

    assert body["status"] == "failed"
    assert body["failure"] == "supply_unpaid"
    for leak in ("price_per_call_usd", "free_allowance", "payment channel", "402"):
        assert leak not in body["error"], f"the desk leaked its supplier terms: {leak}"

    failure = client.get("/api/public/health").json()["supply"]["last_failure"]
    assert failure["kind"] == "supply_unpaid"
    assert "payment_required" in failure["detail"], "the operator still needs the whole text"


def test_health_and_status(client: TestClient) -> None:
    health = client.get("/api/public/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["hub_mode"] == "fixture"
    assert body["pay_mode"] == "fixture"
    status = client.get("/api/public/status")
    assert status.json()["operates_satellites"] is False
    assert "insurer" in status.json()["not"]
    assert status.json()["hub_mode"] == "fixture"
    assert status.json()["pay_mode"] == "fixture"
    assert status.json()["invokes_hub"] is False
    assert status.json()["last_completed_run_at"]


def test_sample_brief_is_public(client: TestClient) -> None:
    response = client.get("/api/public/sample-brief")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == BRIEF_ID
    assert "NOT A PERIMETER" in body["badges"]


def test_sample_brief_without_seeded_row(db: Session, client: TestClient) -> None:
    row = db.get(Brief, BRIEF_ID)
    if row is not None:
        db.delete(row)
        db.commit()
    response = client.get("/api/public/sample-brief")
    assert response.status_code == 200
    body = response.json()
    assert body.get("missing") is not True
    assert "NOT A PERIMETER" in body["badges"]
    assert body["hotspots"]


def test_login_and_desk_flow(client: TestClient) -> None:
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    watches = client.get("/api/watches", headers=headers)
    assert watches.status_code == 200
    assert any(w["id"] == WATCH_ID for w in watches.json())

    ran = client.post(f"/api/watches/{WATCH_ID}/run", headers=headers)
    assert ran.status_code == 200
    payload = ran.json()
    assert payload["status"] == "completed"
    assert payload["evidence_status"] == "live_evidence"
    assert payload["brief_id"]

    brief = client.get(f"/api/briefs/{payload['brief_id']}", headers=headers)
    assert brief.status_code == 200
    assert brief.json()["receipt"]["signature_status"] == "signed"

    archive = client.get("/api/archive", headers=headers)
    assert len(archive.json()) >= 2

    usage = client.get("/api/billing/usage", headers=headers)
    assert usage.json()["plan"] == "team"
    assert usage.json()["runs"] >= 2


def test_rejects_bad_bbox(client: TestClient) -> None:
    token = _login(client)
    response = client.post(
        "/api/watches",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Too Big",
            "west": -130,
            "south": 10,
            "east": -70,
            "north": 55,
        },
    )
    assert response.status_code == 422


def test_engine_persists_run(db: Session, client: TestClient) -> None:
    token = _login(client)
    client.post(f"/api/watches/{WATCH_ID}/run", headers={"Authorization": f"Bearer {token}"})
    assert db.query(Run).count() >= 2
    assert db.query(Brief).count() >= 2


def test_unauthenticated_archive_is_blocked(client: TestClient) -> None:
    assert client.get("/api/archive").status_code == 401


def test_rejects_email_delivery(client: TestClient) -> None:
    token = _login(client)
    response = client.post(
        "/api/watches",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Mail watch",
            "west": -122.5,
            "south": 37.0,
            "east": -121.5,
            "north": 38.0,
            "email_to": "alerts@example.com",
        },
    )
    assert response.status_code == 400
    assert "email delivery is not available" in response.text


def test_sample_share_token_is_public_and_unlisted(client: TestClient) -> None:
    listed = client.get(f"/api/public/briefs/{BRIEF_ID}")
    assert listed.status_code == 404
    shared = client.get(f"/api/public/briefs/{SAMPLE_SHARE_TOKEN}")
    assert shared.status_code == 200
    assert shared.json()["id"] == BRIEF_ID
    assert shared.headers.get("x-robots-tag", "").startswith("noindex")
    private = client.get(f"/api/briefs/{BRIEF_ID}")
    assert private.status_code == 401


def test_new_brief_gets_unguessable_share_link(client: TestClient, db: Session) -> None:
    token = _login(client)
    ran = client.post(f"/api/watches/{WATCH_ID}/run", headers={"Authorization": f"Bearer {token}"})
    brief_id = ran.json()["brief_id"]
    db.expire_all()
    brief = db.get(Brief, brief_id)
    assert brief is not None
    assert brief.share_token
    assert brief.share_token != brief_id
    assert brief.share_token.startswith("shr_")
    pub = client.get(f"/api/public/briefs/{brief.share_token}")
    assert pub.status_code == 200
    assert pub.json()["id"] == brief_id


def test_smoke_layer_is_optional_and_honest(client: TestClient) -> None:
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/watches",
        headers=headers,
        json={
            "name": "Smoke layer box",
            "west": -122.5,
            "south": 37.0,
            "east": -121.5,
            "north": 38.0,
            "policy": "always_brief",
            "layers": ["fire", "weather", "smoke"],
        },
    )
    assert created.status_code == 201
    ran = client.post(f"/api/watches/{created.json()['id']}/run", headers=headers)
    assert ran.status_code == 200
    brief = client.get(f"/api/briefs/{ran.json()['brief_id']}", headers=headers).json()
    assert "atlas.smoke.operations@v1" in (brief.get("skus_used") or [])
    assert brief["smoke_disclaimer"].startswith("HMS smoke")
    assert "PM2.5" in brief["smoke_disclaimer"]
