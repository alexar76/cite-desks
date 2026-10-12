from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .models import DeskGrant
from .plans import PLANS
from .security import hash_desk_key, new_desk_key, new_id


class GrantError(ValueError):
    pass


def mint_grant(
    db: Session,
    *,
    plan: str,
    days: int,
    payment_ref: str,
) -> tuple[DeskGrant, str]:
    if plan not in PLANS:
        raise GrantError("unknown plan")
    existing = db.query(DeskGrant).filter(DeskGrant.payment_ref == payment_ref).one_or_none()
    if existing:
        raise GrantError("payment_ref already minted")
    key = new_desk_key()
    now = datetime.now(timezone.utc)
    grant = DeskGrant(
        id=new_id("dsk"),
        key_hash=hash_desk_key(key),
        payment_ref=payment_ref,
        plan=plan,
        days=days,
        created_at=now,
        expires_at=now + timedelta(days=days + 14),
    )
    db.add(grant)
    db.flush()
    return grant, key
