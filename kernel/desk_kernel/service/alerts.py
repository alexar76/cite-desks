from __future__ import annotations

import json
from typing import Any

import httpx

from desk_kernel.claim import ClaimClass
from desk_kernel.hmac import sign_webhook
from desk_kernel.ids import new_id
from urllib.parse import urlparse, urlunparse

from desk_kernel.webhooks import UnsafeWebhook, resolve_safe_webhook


def deliver(
    *,
    claim: ClaimClass,
    watch: Any,
    brief: dict[str, Any],
    public_url: str,
    share_token: str = "",
) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    path = f"/b/{share_token}" if share_token else "/login"
    link = f"{public_url.rstrip('/')}{path}"
    delta = brief.get("delta") or {}
    delta_line = f"\nDelta: {delta['summary']}" if delta.get("summary") else ""
    text = (
        f"{claim.product_name} alert · {brief['watch']['name']}\n"
        f"{brief['evidence_status']} · {brief.get('live_count', 0)} LIVE"
        f"{delta_line}\n"
        f"{brief['legal_strip']}\n{link}"
    )
    if watch.slack_webhook:
        logs.append(_post_json(watch.slack_webhook, {"text": text}, channel="slack"))
    if watch.https_webhook:
        body = json.dumps(
            {
                "event": claim.event_name,
                "brief_id": brief["id"],
                "watch_id": watch.id,
                "evidence_status": brief["evidence_status"],
                "live_count": brief.get("live_count", 0),
                "link": link,
            },
            separators=(",", ":"),
        ).encode()
        headers = {"Content-Type": "application/json"}
        if watch.webhook_secret:
            headers[claim.signature_header] = sign_webhook(watch.webhook_secret, body)
        logs.append(_post_bytes(watch.https_webhook, body, headers, channel="webhook"))
    return logs


def _pinned_post(url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
    """POST to the address the guard vetted, keeping the name for Host, SNI and the cert."""
    from desk_kernel.service.config import get_settings

    if (get_settings().desk_mode or "").strip().lower() == "demo":
        # The demo desk publishes its owner login, so its webhooks are anyone's outbound POST.
        raise UnsafeWebhook("webhook delivery is off on the demo desk")
    raw, ip = resolve_safe_webhook(url)
    parsed = urlparse(raw)
    host = parsed.hostname or ""
    netloc = (f"[{ip}]" if ":" in ip else ip) + (f":{parsed.port}" if parsed.port else "")
    target = urlunparse(parsed._replace(netloc=netloc))
    with httpx.Client(timeout=8.0, follow_redirects=False) as client:
        return client.post(target, content=content, headers={**headers, "Host": parsed.netloc},
                           extensions={"sni_hostname": host})


def _post_json(url: str, payload: dict[str, Any], channel: str) -> dict[str, Any]:
    try:
        response = _pinned_post(url, content=json.dumps(payload).encode(),
                                headers={"Content-Type": "application/json"})
        return {"id": new_id("dlv"), "channel": channel, "ok": response.is_success, "detail": f"http {response.status_code}"}
    except UnsafeWebhook as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}
    except httpx.HTTPError as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}


def _post_bytes(url: str, body: bytes, headers: dict[str, str], channel: str) -> dict[str, Any]:
    try:
        response = _pinned_post(url, content=body, headers=headers)
        return {"id": new_id("dlv"), "channel": channel, "ok": response.is_success, "detail": f"http {response.status_code}"}
    except UnsafeWebhook as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}
    except httpx.HTTPError as exc:
        return {"id": new_id("dlv"), "channel": channel, "ok": False, "detail": str(exc)}
