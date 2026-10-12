from __future__ import annotations

import logging
from datetime import datetime, timezone

from desk_kernel.supply import failure_summary, note_supply_failure
from sqlalchemy.orm import Session

from . import alerts
from .briefs import SKU_FIRE, SKU_SMOKE, SKU_WATCHBOX, build_brief, should_alert, sku_cogs
from .config import get_settings
from .geo import in_quiet_hours
from .hub import HubClient, HubError
from .models import Brief, DeliveryLog, Run, UsageEvent, Watch, Workspace
from .plans import effective_plan
from .security import new_id, new_share_token

log = logging.getLogger(__name__)


class EngineError(RuntimeError):
    pass


def monthly_run_count(db: Session, workspace_id: str) -> int:
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Run)
        .filter(
            Run.workspace_id == workspace_id,
            Run.status != "failed",
            Run.started_at >= start,
        )
        .count()
    )


def execute_watch(db: Session, watch: Watch, *, client: HubClient | None = None) -> Run:
    settings = get_settings()
    hub = client or HubClient()
    workspace = db.get(Workspace, watch.workspace_id)
    plan = effective_plan(workspace)
    if plan["runs"] <= 0:
        raise EngineError("plan expired for this workspace")
    if monthly_run_count(db, watch.workspace_id) >= plan["runs"]:
        raise EngineError("run quota exhausted for this workspace")

    run = Run(
        id=new_id("run"),
        workspace_id=watch.workspace_id,
        watch_id=watch.id,
        status="running",
        skus_used=[],
    )
    db.add(run)
    db.flush()

    bbox = {"west": watch.west, "south": watch.south, "east": watch.east, "north": watch.north}
    skus: list[str] = []
    snapshot: dict | None = None

    try:
        if watch.policy == "on_match":
            check = hub.watchbox_check(bbox, layers=["fire"])
            run.raw_watchbox = check
            skus.append(SKU_WATCHBOX)
            live_hits = int(check.get("live_match_count") or 0)
            if live_hits <= 0:
                snapshot = {
                    "ok": True,
                    "summary": "Watchbox check found no LIVE fire matches.",
                    "evidence": {"live_fire_detection_count": 0},
                    "hotspots": [],
                    "limitations": [],
                    "receipt": check.get("receipt"),
                }
            else:
                snapshot = hub.fire_weather(bbox)
                skus.append(SKU_FIRE)
        else:
            snapshot = hub.fire_weather(bbox)
            skus.append(SKU_FIRE)
    except HubError as exc:
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        run.skus_used = skus
        db.commit()
        db.refresh(run)
        summary = failure_summary(run.error)
        note_supply_failure(run.finished_at, summary["kind"], run.error)
        # A desk that cannot buy evidence still sells plans, so this cannot be a row in a
        # table nobody reads: the customer sees a failed run and assumes it is them.
        log.error("hub: run %s could not buy evidence (%s): %s", run.id, summary["kind"], run.error)
        return run

    smoke_snapshot = None
    if "smoke" in (watch.layers or []):
        hotspots = (snapshot or {}).get("hotspots") or []
        live = [h for h in hotspots if h.get("live") and str(h.get("mode") or "").lower() != "sim"]
        target = live[0] if live else None
        lat = float(target["lat"]) if target and target.get("lat") is not None else (watch.south + watch.north) / 2
        lon = float(target["lon"]) if target and target.get("lon") is not None else (watch.west + watch.east) / 2
        try:
            smoke_snapshot = hub.invoke(SKU_SMOKE, {"lat": lat, "lon": lon})
            skus.append(SKU_SMOKE)
        except HubError:
            smoke_snapshot = {
                "ok": False,
                "capability_id": SKU_SMOKE,
                "refuse_reason": "smoke operations unavailable; fire brief stands without it",
            }

    run.raw_fire_weather = snapshot
    previous = (
        db.query(Brief)
        .join(Run, Brief.run_id == Run.id)
        .filter(
            Brief.watch_id == watch.id,
            Brief.workspace_id == watch.workspace_id,
            Run.status == "completed",
            Run.id != run.id,
        )
        .order_by(Run.started_at.desc())
        .first()
    )
    brief_payload = build_brief(
        watch={
            "id": watch.id,
            "name": watch.name,
            "west": watch.west,
            "south": watch.south,
            "east": watch.east,
            "north": watch.north,
            "timezone": watch.timezone,
        },
        snapshot=snapshot or {},
        run_id=run.id,
        brief_id=new_id("brf"),
        skus_used=skus,
        previous_brief=previous.payload if previous else None,
    )
    if smoke_snapshot is not None:
        brief_payload["smoke"] = smoke_snapshot
        brief_payload["smoke_disclaimer"] = (
            "HMS smoke is a qualitative North America polygon. Not measured PM2.5, "
            "not a fire perimeter, not an evacuation order."
        )
    share_token = new_share_token()
    brief = Brief(
        id=brief_payload["id"],
        run_id=run.id,
        workspace_id=watch.workspace_id,
        watch_id=watch.id,
        payload=brief_payload,
        share_token=share_token,
    )
    db.add(brief)

    run.skus_used = skus
    run.cogs_usd = sku_cogs(skus)
    run.evidence_status = brief_payload["evidence_status"]
    would_alert = should_alert(
        brief_payload,
        live_hotspots_threshold=watch.alert_live_hotspots,
        brightness_k=watch.alert_brightness_k,
    )
    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    watch.last_run_at = run.finished_at

    for sku in skus:
        db.add(
            UsageEvent(
                id=new_id("use"),
                workspace_id=watch.workspace_id,
                kind="hub_invoke",
                sku=sku,
                amount_usd=sku_cogs([sku]),
                meta={"run_id": run.id},
            )
        )

    if would_alert and in_quiet_hours(watch.quiet_hours, watch.timezone, run.finished_at):
        run.alerted = False
        db.add(
            DeliveryLog(
                id=new_id("dlv"),
                run_id=run.id,
                channel="quiet",
                ok=True,
                detail="suppressed during quiet hours",
            )
        )
    elif would_alert:
        run.alerted = True
        for item in alerts.deliver(
            watch=watch,
            brief=brief_payload,
            public_url=settings.public_url,
            share_token=share_token,
            db=db,
        ):
            db.add(
                DeliveryLog(
                    id=item["id"],
                    run_id=run.id,
                    channel=item["channel"],
                    ok=item["ok"],
                    detail=item["detail"],
                )
            )
    else:
        run.alerted = False

    db.commit()
    db.refresh(run)
    return run
