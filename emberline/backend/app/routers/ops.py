from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..ops import dashboard
from ..security import (
    OPS_COOKIE_NAME,
    allow_login_attempt,
    create_ops_token,
    ops_cookie_kwargs,
    ops_secret,
    require_ops,
    secret_matches,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])


class OpsLoginIn(BaseModel):
    secret: str = Field(min_length=8, max_length=200)


@router.post("/login")
def login(body: OpsLoginIn, request: Request, response: Response) -> dict:
    expected = ops_secret()
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ops is not configured")
    ip = request.client.host if request.client else "unknown"
    if not allow_login_attempt(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many sign-in attempts")
    if not secret_matches(body.secret.strip(), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid ops secret")
    response.set_cookie(value=create_ops_token(), **ops_cookie_kwargs())
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(OPS_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(_: bool = Depends(require_ops)) -> dict:
    return {"ok": True, "role": "ops"}


@router.get("/dashboard")
def ops_dashboard(_: bool = Depends(require_ops), db: Session = Depends(get_db)) -> dict:
    return dashboard(db)
