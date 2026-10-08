from types import SimpleNamespace

from app.alerts import deliver
from app.security import sign_webhook, verify_password, hash_password


def test_webhook_hmac_is_stable() -> None:
    body = b'{"event":"emberline.alert"}'
    first = sign_webhook("secret", body, ts=1_700_000_000)
    second = sign_webhook("secret", body, ts=1_700_000_000)
    assert first == second
    assert first.startswith("t=1700000000,v1=")
    assert sign_webhook("other", body, ts=1_700_000_000) != first
    assert sign_webhook("secret", body, ts=1_700_000_001) != first


def test_password_roundtrip() -> None:
    stored = hash_password("emberline-demo")
    assert verify_password("emberline-demo", stored)
    assert not verify_password("wrong", stored)


def test_alert_link_uses_share_path_and_ignores_email(monkeypatch) -> None:
    captured: dict = {}

    def fake_post_json(url, payload, channel):
        captured["text"] = payload["text"]
        return {"id": "dlv_1", "channel": channel, "ok": True, "detail": "http 200"}

    monkeypatch.setattr("app.alerts._post_json", fake_post_json)
    watch = SimpleNamespace(
        slack_webhook="https://hooks.slack.com/services/fake",
        https_webhook="",
        email_to="nobody@example.com",
        webhook_secret="",
        name="CA box",
    )
    brief = {
        "id": "brf_x",
        "watch": {"name": "CA box"},
        "evidence_status": "live_evidence",
        "live_fire_detection_count": 2,
        "legal_strip": "NOT A PERIMETER",
        "delta": {},
    }
    logs = deliver(
        watch=watch,
        brief=brief,
        public_url="https://emberlinedesk.com",
        share_token="shr_unlisted_token",
    )
    assert [item["channel"] for item in logs] == ["slack"]
    assert "https://emberlinedesk.com/b/shr_unlisted_token" in captured["text"]
    assert "/briefs/brf_x" not in captured["text"]
    email_only = SimpleNamespace(
        slack_webhook="",
        https_webhook="",
        email_to="nobody@example.com",
        webhook_secret="",
        name="CA box",
    )
    assert deliver(watch=email_only, brief=brief, public_url="https://emberlinedesk.com", share_token="shr_x") == []

