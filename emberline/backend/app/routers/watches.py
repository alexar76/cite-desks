from desk_kernel.supply import failure_summary
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine import EngineError, execute_watch
from ..geo import BBoxError, parse_cron_or_interval, validate_bbox
from ..models import Run, User, Watch, Workspace
from ..plans import effective_plan
from ..schemas import WatchCreated, WatchIn, WatchOut
from ..security import current_user, new_id, require_role
from ..webhooks import UnsafeWebhook, assert_safe_webhook_url

router = APIRouter(prefix="/api/watches", tags=["watches"])


@router.get("", response_model=list[WatchOut])
def list_watches(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[WatchOut]:
    rows = (
        db.query(Watch)
        .filter(Watch.workspace_id == user.workspace_id)
        .order_by(Watch.created_at.desc())
        .all()
    )
    return [_watch_out(w) for w in rows]


@router.post("", response_model=WatchCreated, status_code=201)
def create_watch(
    body: WatchIn,
    user: User = Depends(require_role("owner", "analyst")),
    db: Session = Depends(get_db),
) -> WatchCreated:
    workspace = db.get(Workspace, user.workspace_id)
    plan = effective_plan(workspace)
    existing = db.query(Watch).filter(Watch.workspace_id == user.workspace_id).count()
    if plan["watches"] <= 0:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "plan expired for this workspace")
    if existing >= plan["watches"]:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "watch cap reached for this plan")
    try:
        bbox = validate_bbox(body.west, body.south, body.east, body.north)
        schedule = parse_cron_or_interval(body.schedule)
        _validate_delivery(body)
    except (BBoxError, ValueError, UnsafeWebhook) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    secret = new_id("whsec")
    watch = Watch(
        id=new_id("wat"),
        workspace_id=user.workspace_id,
        name=body.name,
        layers=body.layers,
        timezone=body.timezone,
        schedule=schedule,
        quiet_hours=body.quiet_hours,
        status=body.status,
        policy=body.policy,
        alert_live_hotspots=body.alert_live_hotspots,
        alert_brightness_k=body.alert_brightness_k,
        slack_webhook=body.slack_webhook,
        email_to="",
        https_webhook=body.https_webhook,
        webhook_secret=secret,
        **bbox,
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return _watch_created(watch, secret)


@router.get("/{watch_id}", response_model=WatchOut)
def get_watch(watch_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> WatchOut:
    return _watch_out(_owned(db, user, watch_id))


@router.patch("/{watch_id}", response_model=WatchOut)
def patch_watch(
    watch_id: str,
    body: WatchIn,
    user: User = Depends(require_role("owner", "analyst")),
    db: Session = Depends(get_db),
) -> WatchOut:
    watch = _owned(db, user, watch_id)
    try:
        bbox = validate_bbox(body.west, body.south, body.east, body.north)
        watch.schedule = parse_cron_or_interval(body.schedule)
        _validate_delivery(body)
    except (BBoxError, ValueError, UnsafeWebhook) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    watch.name = body.name
    watch.layers = body.layers
    watch.timezone = body.timezone
    watch.quiet_hours = body.quiet_hours
    watch.status = body.status
    watch.policy = body.policy
    watch.alert_live_hotspots = body.alert_live_hotspots
    watch.alert_brightness_k = body.alert_brightness_k
    watch.slack_webhook = body.slack_webhook
    watch.email_to = ""
    watch.https_webhook = body.https_webhook
    for key, value in bbox.items():
        setattr(watch, key, value)
    db.commit()
    db.refresh(watch)
    return _watch_out(watch)


@router.post("/{watch_id}/run")
def run_now(
    watch_id: str,
    user: User = Depends(require_role("owner", "analyst")),
    db: Session = Depends(get_db),
) -> dict:
    watch = _owned(db, user, watch_id)
    try:
        run = execute_watch(db, watch)
    except EngineError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
    brief = run.brief
    failure = failure_summary(run.error)
    return {
        "run_id": run.id,
        "brief_id": brief.id if brief else None,
        "status": run.status,
        "evidence_status": run.evidence_status,
        "alerted": run.alerted,
        "cogs_usd": run.cogs_usd,
        # The upstream's raw refusal names its own prices and billing options; it stays in
        # `run.error` for the operator. The customer gets the part that concerns them.
        "error": failure["message"],
        "failure": failure["kind"],
    }


@router.get("/{watch_id}/runs")
def watch_runs(
    watch_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _owned(db, user, watch_id)
    rows = (
        db.query(Run)
        .filter(Run.watch_id == watch_id, Run.workspace_id == user.workspace_id)
        .order_by(Run.started_at.desc())
        .limit(100)
        .all()
    )
    return [_run_out(r) for r in rows]


def _validate_delivery(body: WatchIn) -> None:
    if (body.email_to or "").strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "email delivery is not available; use slack or https webhook",
        )
    if body.slack_webhook:
        assert_safe_webhook_url(body.slack_webhook)
    if body.https_webhook:
        assert_safe_webhook_url(body.https_webhook)


def _owned(db: Session, user: User, watch_id: str) -> Watch:
    watch = db.get(Watch, watch_id)
    if watch is None or watch.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "watch not found")
    return watch


def _watch_out(watch: Watch) -> WatchOut:
    return WatchOut.model_validate(watch).model_copy(update={"has_webhook_secret": bool(watch.webhook_secret)})


def _watch_created(watch: Watch, secret: str) -> WatchCreated:
    return WatchCreated.model_validate(watch).model_copy(
        update={"has_webhook_secret": True, "webhook_secret": secret}
    )


def _run_out(run: Run) -> dict:
    return {
        "id": run.id,
        "watch_id": run.watch_id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "status": run.status,
        "evidence_status": run.evidence_status,
        "skus_used": run.skus_used,
        "cogs_usd": run.cogs_usd,
        "alerted": run.alerted,
        "brief_id": run.brief.id if run.brief else None,
    }
