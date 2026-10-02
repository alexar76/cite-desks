from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import basepay
from ..config import get_settings
from ..db import get_db
from ..grants import GrantError, mint_grant
from ..plans import PLANS

router = APIRouter(prefix="/api/pay", tags=["pay"])


class MintIn(BaseModel):
    plan: str = "solo"
    days: int = Field(default=30, ge=1, le=366)
    payment_ref: str = Field(min_length=4, max_length=80)


@router.get("/status")
def pay_status() -> dict:
    settings = get_settings()
    rail = basepay.rail_public()
    return {
        "mint_configured": bool(settings.pay_mint_secret),
        "mode": "usdc_base" if rail["enabled"] else "manual",
        "plans": list(PLANS.keys()),
        "base": rail,
    }


@router.post("/mint")
def mint(
    body: MintIn,
    db: Session = Depends(get_db),
    x_emberline_mint: str | None = Header(default=None),
) -> dict:
    settings = get_settings()
    if not settings.pay_mint_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "PAY_MINT_SECRET is not configured")
    if not x_emberline_mint or x_emberline_mint != settings.pay_mint_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid mint secret")
    try:
        grant, key = mint_grant(db, plan=body.plan, days=body.days, payment_ref=body.payment_ref)
        db.commit()
    except GrantError as exc:
        code = status.HTTP_409_CONFLICT if "already" in str(exc) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, str(exc)) from exc
    return {
        "grant_id": grant.id,
        "desk_key": key,
        "plan": grant.plan,
        "days": grant.days,
        "expires_at": grant.expires_at.isoformat(),
        "shown_once": True,
    }
