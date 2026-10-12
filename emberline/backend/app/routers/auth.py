from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..brand import ANON_MAIL_DOMAIN
from ..db import get_db
from ..models import BaseInvoice, DeskGrant, User, Workspace
from ..plans import PLANS, plan_is_expired
from ..schemas import LoginIn, TokenOut
from ..security import (
    allow_login_attempt,
    create_token,
    current_user,
    hash_desk_key,
    hash_password,
    new_id,
    session_cookie_kwargs,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RedeemIn(BaseModel):
    desk_key: str = Field(min_length=12, max_length=120)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    ip = request.client.host if request.client else "unknown"
    if not allow_login_attempt(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many sign-in attempts")
    user = db.query(User).filter(User.email == str(body.email).lower()).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token = create_token(user)
    response.set_cookie(value=token, **session_cookie_kwargs())
    return TokenOut(access_token=token, user=_user_payload(user, db))


@router.post("/redeem", response_model=TokenOut)
def redeem(body: RedeemIn, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    grant = db.query(DeskGrant).filter(DeskGrant.key_hash == hash_desk_key(body.desk_key.strip())).one_or_none()
    now = datetime.now(timezone.utc)
    if grant is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid desk key")
    if grant.expires_at.replace(tzinfo=grant.expires_at.tzinfo or timezone.utc) < now:
        raise HTTPException(status.HTTP_410_GONE, "desk key expired")
    if grant.user_id:
        user = db.get(User, grant.user_id)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid desk key")
    else:
        workspace = Workspace(
            id=new_id("ws"),
            name="Prepaid desk",
            plan=grant.plan if grant.plan in PLANS else "solo",
            billing_email="",
            plan_expires_at=_plan_end(grant, db),
        )
        db.add(workspace)
        db.flush()
        user = User(
            id=new_id("usr"),
            workspace_id=workspace.id,
            email=f"desk-{grant.id}@{ANON_MAIL_DOMAIN}",
            password_hash=hash_password(new_id("pw")),
            name="Desk key holder",
            role="owner",
        )
        db.add(user)
        db.flush()
        grant.workspace_id = workspace.id
        grant.user_id = user.id
        grant.redeemed_at = now
        db.commit()
        db.refresh(user)
        _forget_invoice_key(db, grant.payment_ref)
    token = create_token(user)
    response.set_cookie(value=token, **session_cookie_kwargs())
    return TokenOut(access_token=token, user=_user_payload(user, db))


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(session_cookie_kwargs()["key"], path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _user_payload(user, db)


def _user_payload(user: User, db: Session) -> dict:
    workspace = db.get(Workspace, user.workspace_id)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "workspace": {
            "id": workspace.id if workspace else user.workspace_id,
            "name": workspace.name if workspace else "",
            "plan": workspace.plan if workspace else "solo",
            "plan_expires_at": workspace.plan_expires_at.isoformat() if workspace and workspace.plan_expires_at else None,
            "plan_expired": plan_is_expired(workspace),
        },
    }


def _plan_end(grant: DeskGrant, db: Session) -> datetime:
    invoice = db.get(BaseInvoice, grant.payment_ref)
    start = invoice.paid_at if invoice and invoice.paid_at else datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start + timedelta(days=int(grant.days or 30))


def _forget_invoice_key(db: Session, payment_ref: str) -> None:
    invoice = db.get(BaseInvoice, payment_ref)
    if invoice is None or not invoice.desk_key:
        return
    invoice.desk_key = None
    db.commit()
