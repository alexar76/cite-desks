from types import SimpleNamespace

from app.alerts import deliver
from app.models import PushDevice
from app.security import new_id


def _login(client):
    return client.post("/api/auth/login", json={"email": "owner@emberlinedesk.com", "password": "emberline-demo"}).json()[
        "access_token"
    ]


def test_push_status_disabled_without_vapid(client) -> None:
    token = _login(client)
    status = client.get("/api/push/status", headers={"Authorization": f"Bearer {token}"})
    assert status.status_code == 200
    body = status.json()
    assert body["enabled"] is False
    assert body["public_key"] == ""


def test_push_subscribe_requires_vapid(client) -> None:
    token = _login(client)
    denied = client.post(
        "/api/push/subscribe",
        headers={"Authorization": f"Bearer {token}"},
        json={"endpoint": "https://push.example/" + "x" * 24, "keys": {"p256dh": "k" * 20, "auth": "a" * 12}},
    )
    assert denied.status_code == 503


def test_deliver_sends_workspace_push(monkeypatch, db) -> None:
    captured: dict = {}

    def fake_send(session, **kwargs):
        captured.update(kwargs)
        captured["db"] = session
        return [{"id": "dlv_p", "channel": "push", "ok": True, "detail": "sent"}]

    monkeypatch.setattr("app.push.send_web_pushes", fake_send)
    watch = SimpleNamespace(
        slack_webhook="",
        https_webhook="",
        email_to="",
        webhook_secret="",
        workspace_id="ws_pacific",
        name="CA box",
    )
    logs = deliver(
        watch=watch,
        brief={
            "id": "brf_x",
            "watch": {"name": "CA box"},
            "evidence_status": "live_evidence",
            "live_fire_detection_count": 2,
            "legal_strip": "NOT A PERIMETER",
            "delta": {"summary": "2 appeared"},
        },
        public_url="https://emberlinedesk.com",
        share_token="shr_x",
        db=db,
    )
    assert logs[0]["channel"] == "push"
    assert captured["workspace_id"] == "ws_pacific"
    assert captured["url"] == "/briefs/brf_x"
    assert "LIVE detections" in captured["body"]


def test_send_web_pushes_uses_pywebpush(monkeypatch, db) -> None:
    import sys

    sent: list[dict] = []

    class FakeExc(Exception):
        pass

    class FakeMod:
        WebPushException = FakeExc

        @staticmethod
        def webpush(**kwargs):
            sent.append(kwargs)

    monkeypatch.setitem(sys.modules, "pywebpush", FakeMod)
    monkeypatch.setattr("app.push.vapid_enabled", lambda settings=None: True)
    monkeypatch.setattr(
        "app.push.get_settings",
        lambda: SimpleNamespace(vapid_private_key="priv", vapid_mailto="mailto:desk@emberlinedesk.com"),
    )
    db.add(
        PushDevice(
            id=new_id("psh"),
            workspace_id="ws_pacific",
            user_id="usr_demo",
            endpoint="https://push.example/sub-1",
            p256dh="p256",
            auth="authkey1",
        )
    )
    db.commit()
    from app.push import send_web_pushes

    logs = send_web_pushes(db, workspace_id="ws_pacific", title="T", body="B", url="/desk")
    assert logs[0]["ok"] is True
    assert sent[0]["vapid_private_key"] == "priv"
    assert "T" in sent[0]["data"]
