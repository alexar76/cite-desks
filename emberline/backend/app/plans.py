from __future__ import annotations

from datetime import datetime, timezone

from .models import Workspace

PLANS: dict[str, dict] = {
    "solo": {
        "name": "Solo",
        "price_usd": 49,
        "watches": 2,
        "runs": 200,
        "retention_days": 30,
        "slack": False,
        "api": False,
    },
    "team": {
        "name": "Team",
        "price_usd": 149,
        "watches": 10,
        "runs": 1000,
        "retention_days": 90,
        "slack": True,
        "api": False,
    },
    "desk": {
        "name": "Desk",
        "price_usd": 499,
        "watches": 50,
        "runs": 5000,
        "retention_days": 365,
        "slack": True,
        "api": True,
    },
}

OVERAGE = {
    "atlas.fire.weather@v1": 0.12,
    "atlas.watchbox.check@v1": 0.04,
    "atlas.smoke.operations@v1": 0.16,
}

HUB_COGS = {
    "atlas.fire.weather@v1": 0.08,
    "atlas.watchbox.check@v1": 0.02,
    "atlas.smoke.operations@v1": 0.12,
}


EXPIRED_PLAN: dict = {
    "name": "Expired",
    "price_usd": 0,
    "watches": 0,
    "runs": 0,
    "retention_days": 0,
    "slack": False,
    "api": False,
}


def plan_or_solo(code: str) -> dict:
    return PLANS.get(code, PLANS["solo"])


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def plan_is_expired(workspace: Workspace | None) -> bool:
    if workspace is None:
        return True
    exp = _aware(workspace.plan_expires_at)
    return bool(exp and exp < datetime.now(timezone.utc))


def effective_plan(workspace: Workspace | None) -> dict:
    if workspace is None or plan_is_expired(workspace):
        return EXPIRED_PLAN
    return plan_or_solo(workspace.plan)
