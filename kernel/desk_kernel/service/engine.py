from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from desk_kernel.briefs import build_brief, should_alert
from desk_kernel.claim import ClaimClass
from desk_kernel.geo import in_quiet_hours, interval_minutes, nordic_ais_device_ids, nordic_ais_ok
from desk_kernel.hub import HubClient, HubError
from desk_kernel.ids import new_id, new_share_token
from desk_kernel.policy import should_buy_brief
from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.supply import (
    failure_summary,
    last_supply_credit,
    last_supply_failure,
    note_supply_failure,
)
from desk_kernel.service.models import Brief, DeliveryLog, Run, UsageEvent, Watch, Workspace
from desk_kernel.service.plans import effective_plan
from desk_kernel.service import alerts


log = logging.getLogger(__name__)


class EngineError(RuntimeError):
    pass




def monthly_run_count(db: Session, workspace_id: str) -> int:
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Run)
        .filter(Run.workspace_id == workspace_id, Run.status != "failed", Run.started_at >= start)
        .count()
    )


def _watch_input(claim: ClaimClass, watch: Watch) -> dict:
    if claim.watch_kind == "point":
        return {"lat": watch.lat, "lon": watch.lon, "plant_id": watch.name}
    bbox = {"west": watch.west, "south": watch.south, "east": watch.east, "north": watch.north}
    # A named ATLAS desk preset is the job title. Sending `layers` as well would
    # override it and drop the scope sentence the buyer paid for.
    if claim.brief_preset:
        return {**bbox, "preset": claim.brief_preset}
    if claim.id == "tideline":
        return {**bbox, "layers": list(watch.layers or claim.default_layers)}
    if claim.id == "seamark":
        return {**bbox, "layers": ["ais"]}
    return {**bbox, "layers": list(watch.layers or claim.default_layers)}


def _watch_ref(watch: Watch) -> dict:
    return {
        "id": watch.id,
        "name": watch.name,
        "west": watch.west,
        "south": watch.south,
        "east": watch.east,
        "north": watch.north,
        "lat": watch.lat,
        "lon": watch.lon,
        "timezone": watch.timezone,
    }


def _seamark_snapshot(client: HubClient, payload: dict) -> tuple[dict, int]:
    """Read the correct licensed AIS relay(s), preserving each signed reading."""
    readings: list[dict] = []
    errors: list[str] = []
    for device_id in nordic_ais_device_ids(payload):
        try:
            readings.append(
                client.invoke(
                    "gaia.ais.public.read@v1",
                    {**payload, "device_id": device_id},
                )
            )
        except HubError as exc:
            errors.append(f"{device_id}: {exc}")
    if not readings:
        detail = "; ".join(errors) or "no licensed AIS relay selected"
        raise HubError(f"no LIVE Nordic AIS source delivered: {detail}")
    # build_brief reads `limitations`/`attribution` off THIS wrapper, never off the
    # individual readings. Assigning `errors` here dropped every per-source licence
    # string (Fintraffic CC BY 4.0, Kystverket NLOD 2.0) and left `attribution` null,
    # so a sold cite pack carried none of the credit the licences require.
    merged: list[str] = []
    attributions: list[str] = []
    for reading in readings:
        for note in reading.get("limitations") or []:
            if str(note) not in merged:
                merged.append(str(note))
        credit = reading.get("attribution")
        if credit and str(credit) not in attributions:
            attributions.append(str(credit))
    merged.extend(errors)
    return (
        {
            "ok": True,
            "capability_id": "gaia.ais.public.read@v1",
            "readings": readings,
            "summary": f"{len(readings)} signed Nordic public AIS source(s) delivered.",
            "limitations": merged,
            "attribution": " · ".join(attributions) or None,
        },
        len(readings),
    )


def execute_watch(db: Session, watch: Watch, *, client: HubClient | None = None) -> Run:
    settings = get_settings()
    claim = current_claim()
    hub = client or HubClient(
        claim=claim,
        mode=settings.hub_mode,
        hub_url=settings.hub_url,
        api_key=settings.hub_api_key,
        payment_channel=settings.hub_payment_channel,
        payment_channel_secret=settings.hub_payment_channel_secret,
        gaia_hub_url=settings.gaia_hub_url,
        gaia_hub_api_key=settings.gaia_hub_api_key,
        fixture_loader=_default_fixtures(claim, settings.fixture_dir),
    )
    workspace = db.get(Workspace, watch.workspace_id)
    plan = effective_plan(workspace)
    if plan["runs"] <= 0:
        raise EngineError("plan expired for this workspace")
    if monthly_run_count(db, watch.workspace_id) >= plan["runs"]:
        raise EngineError("run quota exhausted for this workspace")
    if claim.id == "seamark":
        bbox = {"west": watch.west, "south": watch.south, "east": watch.east, "north": watch.north}
        if not nordic_ais_ok(bbox):
            raise EngineError("bbox is outside licensed Finnish or Norwegian waters")

    run = Run(id=new_id("run"), workspace_id=watch.workspace_id, watch_id=watch.id, status="running", skus_used=[])
    db.add(run)
    db.flush()

    skus: list[str] = []
    raw: dict = {}
    snapshot: dict | None = None
    payload_in = _watch_input(claim, watch)

    try:
        if claim.cheap_sku and watch.policy == "on_match":
            check = hub.invoke(claim.cheap_sku, {**payload_in, "layers": list(claim.match_layers)})
            raw["watchbox"] = check
            skus.append(claim.cheap_sku)
            if should_buy_brief(policy=watch.policy, cheap_snapshot=check):
                if claim.id == "seamark":
                    snapshot, source_count = _seamark_snapshot(hub, payload_in)
                    skus.extend([claim.brief_sku] * source_count)
                else:
                    snapshot = hub.invoke(claim.brief_sku, payload_in)
                    skus.append(claim.brief_sku)
            else:
                snapshot = {
                    "ok": True,
                    "summary": "Watchbox check found no LIVE matches.",
                    "evidence": {"live_match_count": 0},
                    "items": [],
                    "limitations": [],
                    "receipt": check.get("receipt"),
                }
        else:
            if claim.id == "seamark":
                snapshot, source_count = _seamark_snapshot(hub, payload_in)
                skus.extend([claim.brief_sku] * source_count)
            else:
                snapshot = hub.invoke(claim.brief_sku, payload_in)
                skus.append(claim.brief_sku)
    except HubError as exc:
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        run.skus_used = skus
        run.raw = raw
        db.commit()
        db.refresh(run)
        summary = failure_summary(run.error)
        note_supply_failure(run.finished_at, summary["kind"], run.error)
        # A desk that cannot buy evidence still takes money for plans, so this cannot be a
        # row in a table nobody reads: the customer sees a failed run and assumes it is them.
        log.error("hub: run %s could not buy evidence (%s): %s", run.id, summary["kind"], run.error)
        return run

    raw["primary"] = snapshot
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
        claim=claim,
        watch=_watch_ref(watch),
        snapshot=snapshot or {},
        run_id=run.id,
        brief_id=new_id("brf"),
        skus_used=skus,
        previous_brief=previous.payload if previous else None,
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
    run.raw = raw
    run.skus_used = skus
    run.cogs_usd = claim.sku_cogs(skus)
    run.evidence_status = brief_payload["evidence_status"]
    would_alert = should_alert(brief_payload, live_threshold=watch.alert_live_threshold)
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
                amount_usd=claim.sku_cogs([sku]),
                meta={"run_id": run.id},
            )
        )

    if would_alert and in_quiet_hours(watch.quiet_hours, watch.timezone, run.finished_at):
        run.alerted = False
        db.add(DeliveryLog(id=new_id("dlv"), run_id=run.id, channel="quiet", ok=True, detail="suppressed during quiet hours"))
    elif would_alert:
        run.alerted = True
        for item in alerts.deliver(claim=claim, watch=watch, brief=brief_payload, public_url=settings.public_url, share_token=share_token):
            db.add(DeliveryLog(id=item["id"], run_id=run.id, channel=item["channel"], ok=item["ok"], detail=item["detail"]))
    else:
        run.alerted = False

    db.commit()
    db.refresh(run)
    return run


def due(watch: Watch) -> bool:
    if watch.status != "active":
        return False
    if watch.last_run_at is None:
        return True
    last = watch.last_run_at if watch.last_run_at.tzinfo else watch.last_run_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last).total_seconds() / 60
    return age >= interval_minutes(watch.schedule)


def _default_fixtures(claim: ClaimClass, fixture_dir: str):
    from desk_kernel.service.fixtures import load_fixture

    def loader(capability_id: str, payload: dict) -> dict:
        return load_fixture(claim, fixture_dir, capability_id, payload)

    return loader
