from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from desk_kernel.chain import RpcError
from desk_kernel.citepack import build_cite_pack
from desk_kernel.geo import BBoxError, PointError, nordic_ais_ok, parse_schedule, validate_bbox, validate_point
from desk_kernel.i18n import LANG_COOKIE, catalog_for, pick_locale
from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.service.db import get_db
from desk_kernel.service.engine import (
    EngineError,
    execute_watch,
    failure_summary,
    last_supply_credit,
    last_supply_failure,
)
from desk_kernel.service.models import BaseInvoice, Brief, DeskGrant, Run, User, Watch, Workspace
from desk_kernel.service.pay import (
    GrantError,
    PayUnavailable,
    confirm_invoice,
    create_invoice,
    fixture_allowed,
    invoice_view,
    last_scan,
    rail_closed_reason,
    rail_enabled,
    rail_public,
    refresh_status,
    simulate_payment,
)
from desk_kernel.service.plans import PLANS, effective_plan
from desk_kernel.service.security import (
    allow_login_attempt,
    allow_pay_attempt,
    allowed_policy,
    client_ip,
    create_token,
    current_user,
    hash_desk_key,
    hash_password,
    new_id,
    session_cookie_kwargs,
    verify_login_password,
)
from desk_kernel.service.seed import BRIEF_ID, seed_demo
from desk_kernel.webhooks import UnsafeWebhook, assert_safe_webhook_url

router = APIRouter()


def _locale(request: Request) -> str:
    return pick_locale(
        current_claim(),
        request.query_params.get("lang") or request.cookies.get(LANG_COOKIE),
        request.headers.get("accept-language"),
    )


def _i18n_cookie(response: JSONResponse, locale: str) -> JSONResponse:
    response.set_cookie(LANG_COOKIE, locale, max_age=365 * 86400, samesite="lax", path="/")
    response.headers["Content-Language"] = locale
    return response


@router.get("/api/public/health")
def health() -> dict:
    settings = get_settings()
    claim = current_claim()
    open_rail = rail_enabled(settings)
    return {
        "ok": True,
        "service": claim.id,
        "demo": settings.is_demo,
        "desk_mode": (settings.desk_mode or "live").lower(),
        "hub_mode": settings.hub_mode,
        "pay_mode": settings.pay_mode,
        "rails": [s["id"] for s in claim.all_skus()],
        # Ops reads this to answer "can this desk take money right now, and will it hand
        # over a key on its own?" A desk that can quote but never settles is worse than
        # one with a closed checkout.
        "checkout": {
            "open": open_rail,
            "reason": "" if open_rail else rail_closed_reason(settings),
            "settlement": (
                "scheduled"
                if open_rail and settings.scheduler_enabled and settings.app_env != "test"
                else "off"
            ),
            "scan_interval_seconds": int(settings.pay_scan_interval_seconds),
            # Proof, not intent: `last_scan.age_seconds` older than the interval (or null on
            # a desk that has been up for a while) means the poll is not running.
            "last_scan": last_scan(),
        },
        # Selling access the desk cannot honour is worse than not selling: a fresh
        # `supply.last_failure` means paid plans are currently buying nothing, and
        # `supply.credit.low` is the warning that arrives while there is still time to act.
        "supply": {"last_failure": last_supply_failure(), "credit": last_supply_credit()},
    }


@router.get("/api/public/status")
def status_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    claim = current_claim()
    locale = _locale(request)
    last = db.query(Run).filter(Run.status == "completed").order_by(Run.finished_at.desc()).first()
    payload = {
        "product": claim.product_name,
        "independent_brand": True,
        "operates_satellites": claim.operates_satellites,
        "powered_by": claim.powered_by,
        "hub_mode": settings.hub_mode,
        "pay_mode": settings.pay_mode,
        "demo": settings.is_demo,
        "desk_mode": (settings.desk_mode or "live").lower(),
        "invokes_hub": settings.hub_mode == "live",
        "last_completed_run_at": last.finished_at.isoformat() if last and last.finished_at else None,
        "not": list(claim.not_list),
        "skus": claim.all_skus(),
        "geography_note": claim.geography_note,
        "legal_strip": claim.legal_strip,
        "tagline": claim.tagline,
        "canonical_host": claim.canonical_host,
        "desk_mail": claim.desk_mail,
        "desk_id": claim.id,
        "watch_kind": claim.watch_kind,
        "schedules": list(claim.schedules),
        "demo_email": claim.demo_email if not settings.is_production else "",
        "default_bbox": list(claim.default_bbox) if claim.default_bbox else None,
        "default_point": list(claim.default_point) if claim.default_point else None,
        "pay": rail_public(),
        "locale": locale,
        "locales": list(claim.locales),
        "host_region": claim.host_region,
        "placement_note": claim.placement_note,
    }
    return _i18n_cookie(JSONResponse(payload), locale)


@router.get("/api/public/i18n")
def i18n_pack(request: Request):
    locale = _locale(request)
    pack = catalog_for(current_claim(), locale)
    return _i18n_cookie(JSONResponse(pack), locale)


@router.get("/api/public/guide")
def public_guide(request: Request):
    locale = _locale(request)
    pack = catalog_for(current_claim(), locale)
    return _i18n_cookie(
        JSONResponse(
            {
                "locale": pack["locale"],
                "locales": pack["locales"],
                "guide": pack["guide"],
                "host_region": pack["host_region"],
                "placement_note": pack["placement_note"],
            }
        ),
        locale,
    )


@router.get("/api/public/sample-brief")
def sample_brief(db: Session = Depends(get_db)) -> dict:
    brief = db.get(Brief, BRIEF_ID)
    if brief is None:
        # seed_demo() is a no-op unless SEED_DEMO is on; this route must never be the
        # thing that provisions a login on a production desk.
        seed_demo(db)
        brief = db.get(Brief, BRIEF_ID)
    return brief.payload if brief else {}


@router.get("/api/public/briefs/{token}")
def public_brief(token: str, db: Session = Depends(get_db)):
    brief = db.query(Brief).filter(Brief.share_token == token).one_or_none()
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return JSONResponse(brief.payload, headers={"X-Robots-Tag": "noindex, nofollow"})


@router.post("/api/auth/logout")
def logout():
    claim = current_claim()
    from fastapi.responses import JSONResponse

    response = JSONResponse({"ok": True})
    response.delete_cookie(claim.cookie_name, path="/")
    return response


@router.get("/api/public/sample-cite-pack")
def sample_cite_pack(db: Session = Depends(get_db)) -> Response:
    claim = current_claim()
    brief = db.get(Brief, BRIEF_ID)
    payload = brief.payload if brief else sample_brief(db)
    raw = brief.run.raw if brief and brief.run else {}
    blob = build_cite_pack(claim=claim, brief=payload if isinstance(payload, dict) else {}, raw=raw or {"primary": {}})
    return Response(blob, media_type="application/zip")


@router.get("/api/public/press")
def public_press(request: Request):
    claim = current_claim()
    locale = _locale(request)
    pack = catalog_for(claim, locale)
    press = pack.get("press") or {}
    payload = {
        "product": claim.product_name,
        "tagline": claim.tagline,
        "boilerplate": press.get("boilerplate") or f"{claim.tagline} {claim.legal_strip}",
        "origin": claim.canonical_origin,
        "host": claim.canonical_host,
        "mail": claim.desk_mail,
        "not": list(claim.not_list),
        "badges": list(claim.badges),
        "skus": claim.all_skus(),
        "do": press.get("do")
        or [
            "Citeable LIVE readings for a named watch.",
            "Fail-closed LIVE vs SIM. Empty stays empty.",
            "Independent brand on ATLAS/GAIA rails.",
        ],
        "do_not": press.get("do_not") or [f"Do not say this desk is a {item}." for item in claim.not_list[:4]],
        "facts": [
            ["Product", claim.product_name],
            ["Unit of work", "A named bbox or pin a person owns"],
            ["Artifact", "Brief + cite pack (PDF, JSON, SHA256)"],
            ["Checkout", "USDC on Base; the desk key is issued by the settlement watcher"],
            ["Not", ", ".join(claim.not_list)],
        ],
    }
    return _i18n_cookie(JSONResponse(payload), locale)


@router.get("/api/public/robots.txt")
def robots() -> Response:
    claim = current_claim()
    body = (
        "User-agent: *\nAllow: /\n"
        f"Sitemap: {claim.canonical_origin}/sitemap.xml\n"
    )
    return Response(body, media_type="text/plain")


@router.get("/api/public/sitemap.xml")
def sitemap() -> Response:
    claim = current_claim()
    origin = claim.canonical_origin.rstrip("/")
    paths = ("/", "/sample", "/guide", "/press", "/legal", "/status", "/pay")
    urls = "".join(f"<url><loc>{origin}{path}</loc></url>" for path in paths)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(xml, media_type="application/xml")


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/api/auth/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    claim = current_claim()
    if not allow_login_attempt(client_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limited")
    user = db.query(User).filter(User.email == str(body.email).lower()).one_or_none()
    ok = verify_login_password(body.password, user.password_hash if user else None)
    if user is None or not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token = create_token(user)
    response = JSONResponse({"access_token": token, "desk": claim.id, "user": _user_out(db, user)})
    response.set_cookie(value=token, **session_cookie_kwargs())
    return response


class WatchBody(BaseModel):
    name: str
    west: float | None = None
    south: float | None = None
    east: float | None = None
    north: float | None = None
    lat: float | None = None
    lon: float | None = None
    schedule: str | None = None
    policy: str | None = None
    timezone: str | None = None
    slack_webhook: str = ""
    https_webhook: str = ""


@router.get("/api/watches")
def list_watches(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Watch).filter(Watch.workspace_id == user.workspace_id).all()
    return [_watch_out(w) for w in rows]


@router.post("/api/watches")
def create_watch(body: WatchBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    claim = current_claim()
    plan = effective_plan(user.workspace)
    n = db.query(Watch).filter(Watch.workspace_id == user.workspace_id).count()
    if n >= plan["watches"]:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "watch quota exhausted")
    try:
        if body.https_webhook:
            assert_safe_webhook_url(body.https_webhook)
        if body.slack_webhook:
            assert_safe_webhook_url(body.slack_webhook)
        schedule = parse_schedule(body.schedule or claim.default_schedule, claim.schedules)
        watch = Watch(
            id=new_id("wat"),
            workspace_id=user.workspace_id,
            name=body.name,
            layers=list(claim.default_layers),
            timezone=body.timezone or claim.sample_timezone,
            schedule=schedule,
            policy=allowed_policy(body.policy, claim.default_policy),
            slack_webhook=body.slack_webhook,
            https_webhook=body.https_webhook,
            webhook_secret=new_id("whs")[4:],
        )
        if claim.watch_kind == "point":
            point = validate_point(float(body.lat), float(body.lon))
            watch.lat, watch.lon = point["lat"], point["lon"]
        else:
            box = validate_bbox(
                float(body.west),
                float(body.south),
                float(body.east),
                float(body.north),
                max_span_ew=claim.max_span_ew,
                max_span_ns=claim.max_span_ns,
            )
            if claim.id == "seamark" and not nordic_ais_ok(box):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "bbox is outside licensed Finnish or Norwegian waters")
            watch.west, watch.south, watch.east, watch.north = box_vals(box)
    except (BBoxError, PointError, ValueError, UnsafeWebhook) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except TypeError as exc:
        # WatchBody declares every coordinate as `float | None = None`, so an omitted
        # field reached float(None) -> TypeError, which is not a ValueError and fell
        # through as a 500 with no hint about which field was missing.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "lat/lon are required for a point desk; west/south/east/north for a bbox desk",
        ) from exc
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return _watch_out(watch)


def box_vals(box: dict) -> tuple:
    return box["west"], box["south"], box["east"], box["north"]


@router.post("/api/watches/{watch_id}/run")
def run_watch(watch_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    watch = db.get(Watch, watch_id)
    if watch is None or watch.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "watch not found")
    try:
        run = execute_watch(db, watch)
    except EngineError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
    brief = db.query(Brief).filter(Brief.run_id == run.id).one_or_none()
    failure = failure_summary(run.error)
    return {
        "id": run.id,
        "status": run.status,
        "evidence_status": run.evidence_status,
        "brief_id": brief.id if brief else None,
        # The upstream's raw refusal names its own prices and billing options; it stays in
        # `run.error` for the operator. The customer gets the part that concerns them.
        "error": failure["message"],
        "failure": failure["kind"],
        "skus_used": run.skus_used,
    }


@router.get("/api/briefs/{brief_id}")
def get_brief(brief_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    brief = db.get(Brief, brief_id)
    if brief is None or brief.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brief not found")
    return brief.payload


@router.get("/api/briefs/{brief_id}/cite-pack")
def cite_pack(brief_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    brief = db.get(Brief, brief_id)
    if brief is None or brief.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brief not found")
    raw = brief.run.raw if brief.run else {}
    blob = build_cite_pack(claim=current_claim(), brief=brief.payload, raw=raw or {})
    return Response(blob, media_type="application/zip")


@router.get("/api/archive")
def archive(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Brief).filter(Brief.workspace_id == user.workspace_id).order_by(Brief.created_at.desc()).all()
    return [{"id": b.id, "watch_id": b.watch_id, "evidence_status": b.payload.get("evidence_status"), "created_at": b.created_at.isoformat()} for b in rows]


@router.get("/api/billing/usage")
def usage(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = effective_plan(user.workspace)
    runs = db.query(Run).filter(Run.workspace_id == user.workspace_id, Run.status != "failed").count()
    return {"plan": user.workspace.plan if user.workspace else "solo", "runs": runs, "caps": plan}


class PayBody(BaseModel):
    plan: str = "solo"
    payment_method: str = "usdc_base"


class ConfirmBody(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66)


@router.get("/api/public/pay/status")
def pay_status() -> dict:
    return rail_public()


@router.post("/api/public/pay/invoices")
def pay_invoice(body: PayBody, request: Request, db: Session = Depends(get_db)):
    # Unauthenticated and it burns a finite resource: allocate_amount() has SALT_MAX
    # (10k) distinct amounts per plan inside the TTL, so an unrationed minter could take
    # every slot and make the next real customer's checkout fail. `allow_pay_attempt` was
    # imported here and never called; emberline's equivalent route always gated on it.
    if not allow_pay_attempt(client_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many payment attempts")
    try:
        invoice = create_invoice(db, plan=body.plan, payment_method=body.payment_method)
    except GrantError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except PayUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return invoice_view(invoice, db)


@router.get("/api/public/pay/invoices/{invoice_id}")
def pay_invoice_read(invoice_id: str, db: Session = Depends(get_db)):
    """The buyer's polling endpoint: this is where a settled key becomes visible.

    Without it a paid invoice was a dead end — the key existed on the row and no route
    ever returned it, so completing a purchase required someone to read the database.
    """
    invoice = db.get(BaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    return invoice_view(refresh_status(db, invoice), db)


@router.post("/api/public/pay/invoices/{invoice_id}/confirm")
def pay_invoice_confirm(invoice_id: str, body: ConfirmBody, request: Request, db: Session = Depends(get_db)):
    """Impatient path: a pasted tx hash settles now instead of at the next poll."""
    if not allow_pay_attempt(client_ip(request), limit=30):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many confirmation attempts")
    invoice = db.get(BaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    try:
        invoice = confirm_invoice(db, invoice, body.tx_hash.strip())
    except PayUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except RpcError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return invoice_view(invoice, db)


@router.post("/api/public/pay/invoices/{invoice_id}/fixture")
@router.post("/api/public/pay/invoices/{invoice_id}/simulate")
def pay_fixture(invoice_id: str, db: Session = Depends(get_db)):
    # Off outside fixture mode, and invisible rather than 500: simulate_payment raises a
    # bare PermissionError that FastAPI maps to no status code at all.
    if not fixture_allowed():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    invoice = db.get(BaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    try:
        invoice = simulate_payment(db, invoice)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return invoice_view(invoice, db)


class RedeemBody(BaseModel):
    desk_key: str = Field(min_length=12, max_length=120)


@router.post("/api/auth/redeem")
def redeem(body: RedeemBody, request: Request, db: Session = Depends(get_db)):
    """Turn a paid desk key into a workspace and a session. The last hands-off step.

    A prepaid buyer never talks to a person: the key came from the scanner, and this route
    provisions the seat. Re-redeeming the same key returns the same workspace rather than
    minting a second one, so a double-click is not a second desk.
    """
    claim = current_claim()
    if not allow_login_attempt(client_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limited")
    grant = (
        db.query(DeskGrant)
        .filter(DeskGrant.key_hash == hash_desk_key(body.desk_key.strip()))
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    if grant is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid desk key")
    expires = grant.expires_at if grant.expires_at.tzinfo else grant.expires_at.replace(tzinfo=timezone.utc)
    if expires < now:
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
            plan_expires_at=_plan_end(db, grant),
        )
        db.add(workspace)
        db.flush()
        user = User(
            id=new_id("usr"),
            workspace_id=workspace.id,
            email=f"desk-{grant.id}@{claim.anon_mail_domain}",
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
    response = JSONResponse({"access_token": token, "desk": claim.id, "user": _user_out(db, user)})
    response.set_cookie(value=token, **session_cookie_kwargs())
    return response


def _plan_end(db: Session, grant: DeskGrant) -> datetime:
    """The paid window starts when the money landed, not when the key was pasted."""
    invoice = db.get(BaseInvoice, grant.payment_ref)
    start = invoice.paid_at if invoice and invoice.paid_at else datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start + timedelta(days=int(grant.days or 30))


def _forget_invoice_key(db: Session, payment_ref: str) -> None:
    """Once redeemed, the invoice stops carrying the plaintext key."""
    invoice = db.get(BaseInvoice, payment_ref)
    if invoice is None or not invoice.desk_key:
        return
    invoice.desk_key = None
    db.commit()


def _user_out(db: Session, user: User) -> dict:
    workspace = db.get(Workspace, user.workspace_id)
    plan = effective_plan(workspace)
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
            "caps": plan,
        },
    }


def _watch_out(watch: Watch) -> dict:
    return {
        "id": watch.id,
        "name": watch.name,
        "west": watch.west,
        "south": watch.south,
        "east": watch.east,
        "north": watch.north,
        "lat": watch.lat,
        "lon": watch.lon,
        "schedule": watch.schedule,
        "policy": watch.policy,
        "status": watch.status,
        "layers": watch.layers,
    }
