from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .briefs import SKU_FIRE, SKU_WATCHBOX, build_brief
from .hub import fixture_fire_weather
from .models import Brief, Run, UsageEvent, User, Watch, Workspace
from .brand import DEMO_EMAIL
from .security import hash_password

DEMO_PASSWORD = "emberline-demo"
WS_ID = "ws_pacific"
USER_ID = "usr_demo"
WATCH_ID = "wat_ca_corridor"
RUN_PREV_ID = "run_sample_000"
BRIEF_PREV_ID = "brf_sample_000"
RUN_ID = "run_sample_001"
BRIEF_ID = "brf_sample_001"
SAMPLE_SHARE_TOKEN = "shr_demo_ca_corridor_sample_unlisted"
PRIOR_SHARE_TOKEN = "shr_demo_ca_corridor_prior_unlisted"

CA_BBOX = {"west": -125.0, "south": 32.0, "east": -114.0, "north": 42.0}


def build_sample_artifacts(now: datetime | None = None) -> dict:
    """Fixture brief for the public marketing page. No database, no demo login."""
    now = now or datetime.now(timezone.utc)
    snapshot = fixture_fire_weather(CA_BBOX)
    prior_snapshot = deepcopy(snapshot)
    live = [h for h in (prior_snapshot.get("hotspots") or []) if h.get("live") and h.get("mode") != "sim"]
    if live:
        values = live[0].setdefault("values", {})
        values["brightness_k"] = float(values.get("brightness_k") or 360) - 12
        prior_snapshot["hotspots"] = [
            h for h in prior_snapshot["hotspots"] if h.get("id") not in {live[-1].get("id"), live[-2].get("id")}
        ]
        prior_snapshot["evidence"] = {
            **(prior_snapshot.get("evidence") or {}),
            "live_fire_detection_count": max(
                0, int((snapshot.get("evidence") or {}).get("live_fire_detection_count") or 0) - 2
            ),
            "returned_detection_count": len([h for h in prior_snapshot["hotspots"] if h.get("live")]),
        }
    watch_ref = {
        "id": WATCH_ID,
        "name": "CA Transmission Corridor",
        **CA_BBOX,
        "timezone": "America/Los_Angeles",
    }
    prior_payload = build_brief(
        watch=watch_ref,
        snapshot=prior_snapshot,
        run_id=RUN_PREV_ID,
        brief_id=BRIEF_PREV_ID,
        skus_used=[SKU_WATCHBOX, SKU_FIRE],
        generated_at=now - timedelta(minutes=32),
    )
    brief_payload = build_brief(
        watch=watch_ref,
        snapshot=snapshot,
        run_id=RUN_ID,
        brief_id=BRIEF_ID,
        skus_used=[SKU_WATCHBOX, SKU_FIRE],
        generated_at=now,
        previous_brief=prior_payload,
    )
    return {
        "brief": brief_payload,
        "prior": prior_payload,
        "snapshot": snapshot,
        "prior_snapshot": prior_snapshot,
        "now": now,
    }


def seed_demo(db: Session) -> None:
    if db.get(Workspace, WS_ID):
        _backfill_sample_delta(db)
        _ensure_demo_share_tokens(db)
        return
    sample = build_sample_artifacts()
    now = sample["now"]
    workspace = Workspace(
        id=WS_ID,
        name="Pacific Desk",
        plan="team",
        billing_email=DEMO_EMAIL,
    )
    user = User(
        id=USER_ID,
        workspace_id=WS_ID,
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        name="Desk Owner",
        role="owner",
    )
    watch = Watch(
        id=WATCH_ID,
        workspace_id=WS_ID,
        name="CA Transmission Corridor",
        **CA_BBOX,
        layers=["fire", "weather"],
        timezone="America/Los_Angeles",
        schedule="30m",
        status="active",
        policy="always_brief",
        alert_live_hotspots=1,
        last_run_at=now,
    )
    snapshot = sample["snapshot"]
    prior_snapshot = sample["prior_snapshot"]
    prior_payload = sample["prior"]
    brief_payload = sample["brief"]
    prior_run = Run(
        id=RUN_PREV_ID,
        workspace_id=WS_ID,
        watch_id=WATCH_ID,
        started_at=now - timedelta(minutes=34),
        finished_at=now - timedelta(minutes=32),
        status="completed",
        evidence_status=prior_payload["evidence_status"],
        skus_used=prior_payload["skus_used"],
        cogs_usd=prior_payload["cogs_usd"],
        alerted=False,
        raw_fire_weather=prior_snapshot,
    )
    run = Run(
        id=RUN_ID,
        workspace_id=WS_ID,
        watch_id=WATCH_ID,
        started_at=now - timedelta(minutes=2),
        finished_at=now,
        status="completed",
        evidence_status=brief_payload["evidence_status"],
        skus_used=brief_payload["skus_used"],
        cogs_usd=brief_payload["cogs_usd"],
        alerted=True,
        raw_fire_weather=snapshot,
    )
    prior_brief = Brief(
        id=BRIEF_PREV_ID,
        run_id=RUN_PREV_ID,
        workspace_id=WS_ID,
        watch_id=WATCH_ID,
        payload=prior_payload,
        share_token=PRIOR_SHARE_TOKEN,
    )
    brief = Brief(
        id=BRIEF_ID,
        run_id=RUN_ID,
        workspace_id=WS_ID,
        watch_id=WATCH_ID,
        payload=brief_payload,
        share_token=SAMPLE_SHARE_TOKEN,
    )
    usage = UsageEvent(
        id="use_sample_001",
        workspace_id=WS_ID,
        kind="hub_invoke",
        sku=SKU_FIRE,
        amount_usd=0.08,
        meta={"run_id": RUN_ID},
    )
    db.add(workspace)
    db.flush()
    db.add_all([user, watch])
    db.flush()
    db.add(prior_run)
    db.flush()
    db.add(run)
    db.flush()
    db.add_all([prior_brief, brief, usage])
    db.commit()


def _backfill_sample_delta(db: Session) -> None:
    current = db.get(Brief, BRIEF_ID)
    if current is None:
        return
    payload = current.payload or {}
    if (payload.get("delta") or {}).get("kind") == "versus_prior":
        return
    snapshot = fixture_fire_weather(CA_BBOX)
    prior_snapshot = deepcopy(snapshot)
    live = [h for h in (prior_snapshot.get("hotspots") or []) if h.get("live") and h.get("mode") != "sim"]
    if live:
        values = live[0].setdefault("values", {})
        values["brightness_k"] = float(values.get("brightness_k") or 360) - 12
        prior_snapshot["hotspots"] = [
            h for h in prior_snapshot["hotspots"] if h.get("id") not in {live[-1].get("id"), live[-2].get("id")}
        ]
        prior_snapshot["evidence"] = {
            **(prior_snapshot.get("evidence") or {}),
            "live_fire_detection_count": max(
                0, int((snapshot.get("evidence") or {}).get("live_fire_detection_count") or 0) - 2
            ),
        }
    watch = db.get(Watch, WATCH_ID)
    if watch is None:
        return
    watch_ref = {"id": WATCH_ID, "name": watch.name, **CA_BBOX, "timezone": watch.timezone}
    now = datetime.now(timezone.utc)
    prior_payload = build_brief(
        watch=watch_ref,
        snapshot=prior_snapshot,
        run_id=RUN_PREV_ID,
        brief_id=BRIEF_PREV_ID,
        skus_used=[SKU_WATCHBOX, SKU_FIRE],
        generated_at=now - timedelta(minutes=32),
    )
    if db.get(Run, RUN_PREV_ID) is None:
        db.add(
            Run(
                id=RUN_PREV_ID,
                workspace_id=WS_ID,
                watch_id=WATCH_ID,
                started_at=now - timedelta(minutes=34),
                finished_at=now - timedelta(minutes=32),
                status="completed",
                evidence_status=prior_payload["evidence_status"],
                skus_used=prior_payload["skus_used"],
                cogs_usd=prior_payload["cogs_usd"],
                alerted=False,
                raw_fire_weather=prior_snapshot,
            )
        )
        db.flush()
    if db.get(Brief, BRIEF_PREV_ID) is None:
        db.add(
            Brief(
                id=BRIEF_PREV_ID,
                run_id=RUN_PREV_ID,
                workspace_id=WS_ID,
                watch_id=WATCH_ID,
                payload=prior_payload,
                share_token=PRIOR_SHARE_TOKEN,
            )
        )
    current.payload = build_brief(
        watch=watch_ref,
        snapshot=snapshot,
        run_id=RUN_ID,
        brief_id=BRIEF_ID,
        skus_used=[SKU_WATCHBOX, SKU_FIRE],
        generated_at=now,
        previous_brief=prior_payload,
    )
    db.commit()


def _ensure_demo_share_tokens(db: Session) -> None:
    mapping = {BRIEF_ID: SAMPLE_SHARE_TOKEN, BRIEF_PREV_ID: PRIOR_SHARE_TOKEN}
    dirty = False
    for brief_id, token in mapping.items():
        row = db.get(Brief, brief_id)
        if row is None:
            continue
        if not row.share_token:
            row.share_token = token
            dirty = True
    if dirty:
        db.commit()
