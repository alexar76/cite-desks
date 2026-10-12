from __future__ import annotations

import hashlib
import hmac
import time


def sign_webhook(secret: str, body: bytes, ts: int | None = None) -> str:
    stamped = int(ts if ts is not None else time.time())
    mac = hmac.new(secret.encode(), f"{stamped}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={stamped},v1={mac}"


def verify_webhook(secret: str, body: bytes, header: str, *, max_age_s: int = 300) -> bool:
    raw = (header or "").strip()
    parts = dict(piece.split("=", 1) for piece in raw.split(",") if "=" in piece)
    try:
        stamped = int(parts.get("t") or "")
        given = parts.get("v1") or ""
    except ValueError:
        return False
    if abs(time.time() - stamped) > max_age_s:
        return False
    expected = sign_webhook(secret, body, ts=stamped)
    return hmac.compare_digest(expected, f"t={stamped},v1={given}")
