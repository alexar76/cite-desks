"""Public-reference (demo) vs merchant (live) desk.

`DESK_MODE=demo` is an environment switch, not a synonym for `PAY_MODE=fixture`.
Fixture still quotes a fake USDC amount and hands a key. Demo must not: this host
is a reference app, not a merchant. Live USDC checkout is unchanged when `DESK_MODE=live`.
"""

from __future__ import annotations

DEMO_CHECKOUT_CLOSED = (
    "demo mode: checkout is closed; this host is a reference, not a merchant"
)


def is_demo(settings=None) -> bool:
    try:
        raw = getattr(settings, "desk_mode", "live")
    except Exception:
        return False
    if raw is None:
        return False
    mode = str(raw).strip().lower()
    if mode in {"", "none", "pydanticundefined"}:
        return False
    return mode in {"demo", "reference"}

