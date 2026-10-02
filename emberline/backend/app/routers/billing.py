from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Run, UsageEvent, User, Watch, Workspace
from ..plans import OVERAGE, PLANS, effective_plan, plan_is_expired
from ..security import current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/usage")
def usage(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    workspace = db.get(Workspace, user.workspace_id)
    plan = effective_plan(workspace)
    expired = plan_is_expired(workspace)
    runs = (
        db.query(func.count(Run.id))
        .filter(Run.workspace_id == user.workspace_id, Run.status == "completed")
        .scalar()
        or 0
    )
    watches = db.query(func.count(Watch.id)).filter(Watch.workspace_id == user.workspace_id).scalar() or 0
    cogs = (
        db.query(func.coalesce(func.sum(UsageEvent.amount_usd), 0))
        .filter(UsageEvent.workspace_id == user.workspace_id)
        .scalar()
        or 0
    )
    by_sku = (
        db.query(UsageEvent.sku, func.count(UsageEvent.id), func.sum(UsageEvent.amount_usd))
        .filter(UsageEvent.workspace_id == user.workspace_id)
        .group_by(UsageEvent.sku)
        .all()
    )
    return {
        "plan": workspace.plan if workspace else "solo",
        "plan_expired": expired,
        "plan_expires_at": workspace.plan_expires_at.isoformat() if workspace and workspace.plan_expires_at else None,
        "plan_meta": plan,
        "catalog": PLANS,
        "overage": OVERAGE,
        "watches": watches,
        "runs": runs,
        "cogs_usd": float(cogs),
        "by_sku": [
            {"sku": sku, "count": count, "cogs_usd": float(total or 0)}
            for sku, count, total in by_sku
            if sku
        ],
    }
