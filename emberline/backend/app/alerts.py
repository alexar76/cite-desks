from __future__ import annotations

import json
from typing import Any

import httpx

from .security import new_id, sign_webhook
from .webhooks import UnsafeWebhook, assert_safe_webhook_url


def deliver(
    *,
    watch: Any,
    brief: dict[str, Any],
    public_url: str,
    share_token: str = "",
    db: Any = None,
) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    path = f"/b/{share_token}" if share_token else "/login"
    link = f"{public_url.rstrip('/')}{path}"
    delta = brief.get("delta") or {}
    delta_line = f"\nDelta: {delta['summary']}" if delta.get("summary") else ""
    text = (
        f"Emberline alert · {brief['watch']['name']}\n"
        f"{brief['evidence_status']} · {brief['live_fire_detection_count']} LIVE detections"
        f"{delta_line}\n"
        f"{brief['legal_strip']}\n{link}"
    )
    if watch.slack_webhook:
        logs.append(_post_json(watch.slack_webhook, {"text": text}, channel="slack"))
    if watch.https_webhook:
        body = json.dumps(
            {
                "event": "emberline.alert",
                "brief_id": brief["id"],
                "watch_id": watch.id,
                "evidence_status": brief["evidence_status"],
                "live_fire_detection_count": brief["live_fire_detection_count"],
                "link": link,
            },
            separators=(",", ":"),
        ).encode()
        headers = {"Content-Type": "application/json"}
        if watch.webhook_secret:
            headers["X-Emberline-Signature"] = sign_webhook(watch.webhook_secret, body)
        logs.append(_post_bytes(watch.https_webhook, body, headers, channel="webhook"))
    if db is not None and getattr(watch, "workspace_id", None):
        from .push import send_web_pushes

        logs.extend(
            send_web_pushes(
                db,
                workspace_id=watch.workspace_id,
                title=f"Emberline · {brief['watch']['name']}",
                body=(
                    f"{brief['evidence_status']} · {brief['live_fire_detection_count']} LIVE detections"
                    + (f" · {delta['summary']}" if delta.get("summary") else "")
                )[:180],
                url=f"/briefs/{brief['id']}" if brief.get("id") else "/desk",
            )
        )
    return logs


def _post_json(url: str, payload: dict[str, Any], channel: str) -> dict[str, Any]:
    try:
        assert_safe_webhook_url(url)
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            response = client.post(url, json=payload)
        return {
            "id": new_id("dlv"),
            "channel": channel,
            "ok": response.is_success,
            "detail": f"http {response.status_code}",
        }
    except UnsafeWebhook as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}
    except httpx.HTTPError as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}


def _post_bytes(url: str, body: bytes, headers: dict[str, str], channel: str) -> dict[str, Any]:
    try:
        assert_safe_webhook_url(url)
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            response = client.post(url, content=body, headers=headers)
        return {
            "id": new_id("dlv"),
            "channel": channel,
            "ok": response.is_success,
            "detail": f"http {response.status_code}",
        }
    except UnsafeWebhook as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}
    except httpx.HTTPError as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}
