from app.models import DeskGrant, User


def _ops_login(client):
    return client.post("/api/ops/login", json={"secret": "test-mint"})


def test_ops_rejects_anonymous_and_desk_session(client) -> None:
    assert client.get("/api/ops/dashboard").status_code == 401
    token = client.post("/api/auth/login", json={"email": "owner@emberlinedesk.com", "password": "emberline-demo"}).json()[
        "access_token"
    ]
    denied = client.get("/api/ops/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 401


def test_ops_login_and_dashboard(client, db) -> None:
    bad = client.post("/api/ops/login", json={"secret": "definitely-not"})
    assert bad.status_code == 401
    ok = _ops_login(client)
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    me = client.get("/api/ops/me")
    assert me.status_code == 200
    dash = client.get("/api/ops/dashboard").json()
    assert dash["kpis"]["workspaces"] >= 1
    assert dash["kpis"]["users"] >= 1
    labels = [step["id"] for step in dash["funnel"]]
    assert labels == ["invoice", "paid", "grant", "redeemed", "watch", "run", "alert"]
    assert len(dash["series"]["days"]) == 30
    assert len(dash["series"]["runs"]) == 30
    seats = {row["id"]: row for row in dash["workspaces"]}
    assert "ws_pacific" in seats
    assert seats["ws_pacific"]["watches"] >= 1
    assert seats["ws_pacific"]["runs"] >= 1
    assert all("desk_key" not in row for row in dash["recent_invoices"])
    assert client.get("/api/ops/dashboard", headers={"X-Emberline-Mint": "test-mint"}).status_code == 200


def test_ops_header_secret_without_cookie(client) -> None:
    client.post("/api/ops/logout")
    assert client.get("/api/ops/me").status_code == 401
    assert client.get("/api/ops/dashboard", headers={"X-Emberline-Ops": "test-mint"}).status_code == 200


def test_ops_funnel_counts_minted_grant(client, db) -> None:
    minted = client.post(
        "/api/pay/mint",
        json={"plan": "solo", "days": 7, "payment_ref": "ops-funnel-1"},
        headers={"X-Emberline-Mint": "test-mint"},
    )
    assert minted.status_code == 200
    grant = db.query(DeskGrant).filter(DeskGrant.payment_ref == "ops-funnel-1").one()
    assert grant.redeemed_at is None
    _ops_login(client)
    dash = client.get("/api/ops/dashboard").json()
    funnel = {step["id"]: step["count"] for step in dash["funnel"]}
    assert funnel["grant"] >= 1
    assert dash["kpis"]["grants_unredeemed"] >= 1
    assert db.query(User).count() >= 1
