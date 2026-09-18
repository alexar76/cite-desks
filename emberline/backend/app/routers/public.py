from desk_kernel.supply import last_supply_credit, last_supply_failure
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from .. import basepay
from ..citepack import build_cite_pack
from ..config import get_settings
from ..db import get_db
from ..models import Brief, Run
from ..seed import BRIEF_ID, build_sample_artifacts

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "ok": True,
        "service": "emberline",
        "demo": settings.is_demo,
        "desk_mode": (settings.desk_mode or "live").lower(),
        "hub_mode": settings.hub_mode,
        "pay_mode": settings.pay_mode,
        # Same shape as the sibling desks: one question ("can this desk sell without a
        # human?") answered the same way on every desk, so one deploy check fits the family.
        "checkout": basepay.checkout_state(settings),
        # Selling access the desk cannot honour is worse than not selling: a fresh
        # `supply.last_failure` means paid plans are currently buying nothing, and
        # `supply.credit.low` is the warning that arrives while there is still time to act.
        "supply": {"last_failure": last_supply_failure(), "credit": last_supply_credit()},
        "rails": ["atlas.fire.weather@v1", "atlas.watchbox.check@v1"],
    }


@router.get("/status")
def status_page(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    last = (
        db.query(Run)
        .filter(Run.status == "completed")
        .order_by(Run.finished_at.desc())
        .first()
    )
    return {
        "product": "Emberline Fire Evidence Desk",
        "independent_brand": True,
        "operates_satellites": False,
        "powered_by": "AIMarket ATLAS / GAIA / Hub",
        "hub_mode": settings.hub_mode,
        "pay_mode": settings.pay_mode,
        "demo": settings.is_demo,
        "desk_mode": (settings.desk_mode or "live").lower(),
        "invokes_hub": False,
        "last_completed_run_at": last.finished_at.isoformat() if last and last.finished_at else None,
        "not": [
            "fire perimeter",
            "forecast",
            "evacuation authority",
            "insurer",
            "risk score",
        ],
        "skus": [
            {"id": "atlas.fire.weather@v1", "list_usd": 0.08},
            {"id": "atlas.watchbox.check@v1", "list_usd": 0.02},
        ],
        "copy": "Powered by AIMarket ATLAS/GAIA. We do not operate satellites. This page does not invoke Hub.",
        "locales": ["en", "es", "fr"],
        "host_region": "us",
        "pay": basepay.rail_public(),
    }


@router.get("/sample-brief")
def sample_brief(db: Session = Depends(get_db)) -> dict:
    brief = db.get(Brief, BRIEF_ID)
    if brief is None:
        return build_sample_artifacts()["brief"]
    return brief.payload


@router.get("/briefs/{token}")
def public_brief(token: str, db: Session = Depends(get_db)) -> JSONResponse:
    brief = db.query(Brief).filter(Brief.share_token == token).one_or_none()
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brief not found")
    return JSONResponse(
        content=brief.payload,
        headers={"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "no-store"},
    )


@router.get("/sample-cite-pack")
def sample_cite_pack(db: Session = Depends(get_db)) -> Response:
    brief = db.get(Brief, BRIEF_ID)
    if brief is None:
        sample = build_sample_artifacts()
        payload = build_cite_pack(
            brief=sample["brief"],
            raw_fire_weather=sample["snapshot"],
            raw_watchbox=None,
        )
    else:
        run = db.get(Run, brief.run_id)
        payload = build_cite_pack(
            brief=brief.payload,
            raw_fire_weather=run.raw_fire_weather if run else None,
            raw_watchbox=run.raw_watchbox if run else None,
        )
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="emberline_sample_cite.zip"',
            "Cache-Control": "no-store",
        },
    )
