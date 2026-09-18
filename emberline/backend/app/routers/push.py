from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PushDevice, User
from ..push import vapid_enabled, vapid_public
from ..security import current_user, new_id

router = APIRouter(prefix="/api/push", tags=["push"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=80)


class PushSubscribeIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2000)
    keys: PushKeys


@router.get("/status")
def push_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    enabled = vapid_enabled()
    mine = (
        db.query(PushDevice)
        .filter(PushDevice.user_id == user.id)
        .count()
        if enabled
        else 0
    )
    return {"enabled": enabled, "public_key": vapid_public() if enabled else "", "subscribed": mine > 0}


@router.post("/subscribe")
def subscribe(body: PushSubscribeIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not vapid_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "web push is not configured")
    endpoint = body.endpoint.strip()
    row = db.query(PushDevice).filter(PushDevice.endpoint == endpoint).one_or_none()
    if row is None:
        row = PushDevice(
            id=new_id("psh"),
            workspace_id=user.workspace_id,
            user_id=user.id,
            endpoint=endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
        )
        db.add(row)
    else:
        row.workspace_id = user.workspace_id
        row.user_id = user.id
        row.p256dh = body.keys.p256dh
        row.auth = body.keys.auth
    db.commit()
    return {"ok": True, "subscribed": True}


@router.delete("/subscribe")
def unsubscribe(body: PushSubscribeIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = db.query(PushDevice).filter(PushDevice.endpoint == body.endpoint.strip(), PushDevice.user_id == user.id).one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()
    return {"ok": True, "subscribed": False}
