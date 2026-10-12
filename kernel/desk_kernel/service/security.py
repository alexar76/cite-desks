from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from desk_kernel.hmac import sign_webhook as kernel_sign_webhook
from desk_kernel.ids import hash_desk_key, new_desk_key, new_id, new_share_token
from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.service.db import get_db
from desk_kernel.service.models import User

_bearer = HTTPBearer(auto_error=False)
_ITERATIONS = 210_000
_login_hits: dict[str, list[float]] = {}
_pay_hits: dict[str, list[float]] = {}
_login_lock = Lock()
_POLICIES = frozenset({"on_match", "always_brief"})
# Pre-hashed pad so a missing user still pays PBKDF2 cost.
_DUMMY_HASH = "0" * 32 + "$" + "0" * 64


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return hmac.compare_digest(check.hex(), digest)


def create_token(user: User) -> str:
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_ttl_hours)
    return jwt.encode(
        {"sub": user.id, "ws": user.workspace_id, "role": user.role, "exp": exp},
        settings.jwt_secret,
        algorithm="HS256",
    )


def client_ip(request: Request) -> str:
    """The visitor address the rate limiters bucket on.

    Read the chain from the RIGHT, skipping the proxies we put there ourselves
    (``TRUSTED_PROXY_HOPS``, default 1 = the desk's own web container). The left-most
    entry is whatever the caller chose to send, so keying limits on it let one client
    present a fresh address per request; the hop our own nginx appended cannot be forged.
    """
    chain = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if chain:
        hops = max(0, get_settings().trusted_proxy_hops)
        idx = len(chain) - 1 - hops
        return chain[max(0, min(idx, len(chain) - 1))][:64]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def allowed_policy(value: str | None, default: str) -> str:
    policy = (value or default or "on_match").strip()
    if policy not in _POLICIES:
        raise ValueError("policy must be on_match or always_brief")
    return policy


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    claim = current_claim()
    token = creds.credentials if creds is not None else request.cookies.get(claim.cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in required")
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from exc
    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    workspace = payload.get("ws")
    if workspace and workspace != user.workspace_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    return user


def sign_webhook(secret: str, body: bytes, ts: int | None = None) -> str:
    return kernel_sign_webhook(secret, body, ts)


def mint_key() -> str:
    return new_desk_key(current_claim().key_prefix)


def session_cookie_kwargs() -> dict:
    settings = get_settings()
    claim = current_claim()
    return {
        "key": claim.cookie_name,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure or settings.is_production,
        "max_age": settings.jwt_ttl_hours * 3600,
        "path": "/",
    }


def allow_login_attempt(ip: str) -> bool:
    settings = get_settings()
    return _hit(_login_hits, ip, max(1, settings.login_rate_limit))


def allow_pay_attempt(ip: str, *, limit: int = 8) -> bool:
    return _hit(_pay_hits, ip, limit)


def _hit(bucket: dict[str, list[float]], ip: str, limit: int) -> bool:
    now = time.time()
    with _login_lock:
        recent = [stamp for stamp in bucket.get(ip, []) if now - stamp < 900]
        if len(recent) >= limit:
            bucket[ip] = recent
            return False
        recent.append(now)
        bucket[ip] = recent
        return True


def reset_rate_limits() -> None:
    with _login_lock:
        _login_hits.clear()
        _pay_hits.clear()


def verify_login_password(password: str, stored: str | None) -> bool:
    if stored:
        return verify_password(password, stored)
    verify_password(password, _DUMMY_HASH)
    return False


__all__ = [
    "allow_login_attempt",
    "allow_pay_attempt",
    "allowed_policy",
    "client_ip",
    "create_token",
    "current_user",
    "hash_desk_key",
    "hash_password",
    "mint_key",
    "new_id",
    "new_share_token",
    "reset_rate_limits",
    "session_cookie_kwargs",
    "sign_webhook",
    "verify_login_password",
    "verify_password",
]
