from __future__ import annotations

import hashlib
import secrets


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def new_share_token() -> str:
    return f"shr_{secrets.token_urlsafe(24)}"


def new_desk_key(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(24)}"


def hash_desk_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
