from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .config import get_settings
from .models import PushDevice
from .security import new_id

GONE = {404, 410}


def vapid_enabled(settings=None) -> bool:
    settings = settings or get_settings()
    return bool((settings.vapid_public_key or "").strip() and (settings.vapid_private_key or "").strip())


def vapid_public(settings=None) -> str:
    settings = settings or get_settings()
    return (settings.vapid_public_key or "").strip()


def send_web_pushes(
    db: Session,
    *,
    workspace_id: str,
    title: str,
    body: str,
    url: str,
) -> list[dict[str, Any]]:
    if not vapid_enabled():
        return []
    settings = get_settings()
    private = (settings.vapid_private_key or "").replace("\\n", "\n")
    rows = db.query(PushDevice).filter(PushDevice.workspace_id == workspace_id).all()
    if not rows:
        return []
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return [{"id": new_id("dlv"), "channel": "push", "ok": False, "detail": "pywebpush missing"}]
    payload = json.dumps({"title": title, "body": body, "url": url}, separators=(",", ":"))
    logs: list[dict[str, Any]] = []
    stale: list[PushDevice] = []
    for device in rows:
        try:
            webpush(
                subscription_info={
                    "endpoint": device.endpoint,
                    "keys": {"p256dh": device.p256dh, "auth": device.auth},
                },
                data=payload,
                vapid_private_key=private,
                vapid_claims={"sub": settings.vapid_mailto or "mailto:desk@emberlinedesk.com"},
                ttl=300,
            )
            logs.append({"id": new_id("dlv"), "channel": "push", "ok": True, "detail": "sent"})
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in GONE:
                stale.append(device)
                logs.append({"id": new_id("dlv"), "channel": "push", "ok": False, "detail": f"gone {status}"})
            else:
                logs.append({"id": new_id("dlv"), "channel": "push", "ok": False, "detail": str(exc)[:300]})
        except Exception as exc:  # noqa: BLE001 — delivery must not fail the run
            logs.append({"id": new_id("dlv"), "channel": "push", "ok": False, "detail": str(exc)[:300]})
    for device in stale:
        db.delete(device)
    return logs
