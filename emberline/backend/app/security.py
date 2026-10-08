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

from .config import get_settings
from .db import get_db
from .models import User

_bearer = HTTPBearer(auto_error=False)
_ITERATIONS = 210_000
_login_hits: dict[str, list[float]] = {}
_pay_hits: dict[str, list[float]] = {}
_login_lock = Lock()
COOKIE_NAME = "emberline_session"
OPS_COOKIE_NAME = "emberline_ops"


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


def _token_from_request(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
) -> str | None:
    if creds is not None:
        return creds.credentials
    cookie = request.cookies.get(COOKIE_NAME)
    return cookie or None


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = _token_from_request(request, creds)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in required")
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from exc
    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return user


def require_role(*roles: str):
    def _inner(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return _inner


def sign_webhook(secret: str, body: bytes, ts: int | None = None) -> str:
    from desk_kernel.hmac import sign_webhook as _sign

    return _sign(secret, body, ts)


def hash_desk_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_desk_key() -> str:
    return f"emb_{secrets.token_urlsafe(24)}"


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def new_share_token() -> str:
    return f"shr_{secrets.token_urlsafe(24)}"


def allow_login_attempt(ip: str) -> bool:
    settings = get_settings()
    limit = max(1, settings.login_rate_limit)
    now = time.time()
    with _login_lock:
        recent = [stamp for stamp in _login_hits.get(ip, []) if now - stamp < 900]
        if len(recent) >= limit:
            _login_hits[ip] = recent
            return False
        recent.append(now)
        _login_hits[ip] = recent
        return True


def allow_pay_attempt(ip: str, *, limit: int = 8) -> bool:
    now = time.time()
    with _login_lock:
        recent = [stamp for stamp in _pay_hits.get(ip, []) if now - stamp < 900]
        if len(recent) >= limit:
            _pay_hits[ip] = recent
            return False
        recent.append(now)
        _pay_hits[ip] = recent
        return True


def reset_rate_limits() -> None:
    """Test helper: the buckets are module state and outlive a TestClient."""
    with _login_lock:
        _login_hits.clear()
        _pay_hits.clear()


def session_cookie_kwargs() -> dict:
    settings = get_settings()
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure or settings.is_production,
        "max_age": settings.jwt_ttl_hours * 3600,
        "path": "/",
    }


def ops_secret() -> str:
    settings = get_settings()
    return (settings.ops_secret or settings.pay_mint_secret or "").strip()


def secret_matches(given: str, expected: str) -> bool:
    if not given or not expected or len(given) != len(expected):
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def create_ops_token() -> str:
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_ttl_hours)
    return jwt.encode({"ops": True, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def ops_cookie_kwargs() -> dict:
    settings = get_settings()
    return {
        "key": OPS_COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure or settings.is_production,
        "max_age": settings.jwt_ttl_hours * 3600,
        "path": "/",
    }


def require_ops(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> bool:
    expected = ops_secret()
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ops is not configured")
    header = (request.headers.get("x-emberline-ops") or request.headers.get("x-emberline-mint") or "").strip()
    if header and secret_matches(header, expected):
        return True
    token = request.cookies.get(OPS_COOKIE_NAME) or (creds.credentials if creds else None)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ops sign-in required")
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid ops session") from exc
    if payload.get("ops") is not True:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid ops session")
    return True
