from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from desk_kernel.briefs import build_brief
from desk_kernel.geo import parse_schedule
from desk_kernel.ids import new_id
from desk_kernel.service.config import current_claim, get_settings
from desk_kernel.service.fixtures import load_fixture
from desk_kernel.service.models import Brief, Run, User, Watch, Workspace
from desk_kernel.service.security import hash_password

WS_ID = "ws_demo"
USER_ID = "usr_demo"
WATCH_ID = "wat_demo"
RUN_ID = "run_sample_001"
BRIEF_ID = "brf_sample_001"
SAMPLE_SHARE_TOKEN = "shr_demo_sample_unlisted"


def seed_demo(db: Session) -> None:
    """Plant the demo workspace, owner login and sample brief.

    The guard lives HERE, not only at the startup call site: the unauthenticated
    ``GET /api/public/sample-brief`` also called this, so on a desk deployed with
    ``SEED_DEMO=false`` one anonymous request re-created ``owner@<desk>.com`` with the
    published demo password and a `team`-plan workspace — a working login nobody had
    provisioned. A no-op when demo seeding is off makes that unreachable from any caller.
    """
    if not get_settings().seed_demo:
        return
    claim = current_claim()
    if db.get(Workspace, WS_ID):
        return
    now = datetime.now(timezone.utc)
    workspace = Workspace(id=WS_ID, name=f"{claim.id} desk", plan="team", billing_email=claim.demo_email)
    user = User(
        id=USER_ID,
        workspace_id=WS_ID,
        email=claim.demo_email,
        password_hash=hash_password(claim.demo_password),
        name="Desk Owner",
        role="owner",
    )
    watch_kwargs: dict = {
        "id": WATCH_ID,
        "workspace_id": WS_ID,
        "name": claim.sample_watch_name,
        "layers": list(claim.default_layers),
        "timezone": claim.sample_timezone,
        "schedule": parse_schedule(claim.default_schedule, claim.schedules),
        "status": "active",
        "policy": claim.default_policy,
        "last_run_at": now,
    }
    if claim.watch_kind == "point" and claim.default_point:
        watch_kwargs["lat"], watch_kwargs["lon"] = claim.default_point
    elif claim.default_bbox:
        w, s, e, n = claim.default_bbox
        watch_kwargs.update(west=w, south=s, east=e, north=n)
    watch = Watch(**watch_kwargs)
    snapshot = load_fixture(claim, "", claim.brief_sku, _payload(claim, watch_kwargs))
    brief_payload = build_brief(
        claim=claim,
        watch={"id": WATCH_ID, "name": claim.sample_watch_name, **watch_kwargs},
        snapshot=snapshot,
        run_id=RUN_ID,
        brief_id=BRIEF_ID,
        skus_used=[s for s in (claim.cheap_sku, claim.brief_sku) if s],
    )
    run = Run(
        id=RUN_ID,
        workspace_id=WS_ID,
        watch_id=WATCH_ID,
        status="completed",
        evidence_status=brief_payload["evidence_status"],
        skus_used=brief_payload["skus_used"],
        cogs_usd=brief_payload["cogs_usd"],
        started_at=now,
        finished_at=now,
        raw={"primary": snapshot},
    )
    brief = Brief(
        id=BRIEF_ID,
        run_id=RUN_ID,
        workspace_id=WS_ID,
        watch_id=WATCH_ID,
        payload=brief_payload,
        share_token=SAMPLE_SHARE_TOKEN,
        created_at=now,
    )
    db.add_all([workspace, user, watch, run, brief])
    db.commit()


def _payload(claim, watch_kwargs: dict) -> dict:
    if claim.watch_kind == "point":
        return {"lat": watch_kwargs.get("lat"), "lon": watch_kwargs.get("lon")}
    return {k: watch_kwargs.get(k) for k in ("west", "south", "east", "north")}
