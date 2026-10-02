from __future__ import annotations

from desk_kernel.service.models import Workspace

PLANS: dict[str, dict] = {
    "solo": {"name": "Solo", "price_usd": 49, "watches": 2, "runs": 200, "retention_days": 30},
    "team": {"name": "Team", "price_usd": 149, "watches": 10, "runs": 1000, "retention_days": 90},
    "desk": {"name": "Desk", "price_usd": 499, "watches": 50, "runs": 5000, "retention_days": 365},
}

EXPIRED_PLAN = {**PLANS["solo"], "name": "Expired", "price_usd": 0, "watches": 0, "runs": 0}


def plan_or_solo(code: str) -> dict:
    return PLANS.get(code, PLANS["solo"])


def effective_plan(workspace: Workspace | None) -> dict:
    if workspace is None:
        return EXPIRED_PLAN
    from datetime import datetime, timezone

    exp = workspace.plan_expires_at
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return EXPIRED_PLAN
    return plan_or_solo(workspace.plan)
