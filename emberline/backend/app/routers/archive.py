from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..citepack import build_cite_pack
from ..db import get_db
from ..models import Brief, Run, User, Watch
from ..security import current_user

router = APIRouter(prefix="/api", tags=["archive"])


@router.get("/archive")
def archive(
    watch_id: str | None = None,
    alerted: bool | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(Run).filter(Run.workspace_id == user.workspace_id)
    if watch_id:
        query = query.filter(Run.watch_id == watch_id)
    if alerted is not None:
        query = query.filter(Run.alerted == alerted)
    rows = query.order_by(Run.started_at.desc()).limit(200).all()
    watches = {w.id: w.name for w in db.query(Watch).filter(Watch.workspace_id == user.workspace_id)}
    return [
        {
            "id": run.id,
            "watch_id": run.watch_id,
            "watch_name": watches.get(run.watch_id, ""),
            "started_at": run.started_at,
            "status": run.status,
            "evidence_status": run.evidence_status,
            "alerted": run.alerted,
            "cogs_usd": run.cogs_usd,
            "skus_used": run.skus_used,
            "brief_id": run.brief.id if run.brief else None,
        }
        for run in rows
    ]


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    brief = db.get(Brief, brief_id)
    if brief is None or brief.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brief not found")
    return brief.payload


@router.get("/briefs/{brief_id}/raw")
def get_brief_raw(brief_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    brief = db.get(Brief, brief_id)
    if brief is None or brief.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brief not found")
    run = db.get(Run, brief.run_id)
    return {
        "brief": brief.payload,
        "raw_fire_weather": run.raw_fire_weather if run else None,
        "raw_watchbox": run.raw_watchbox if run else None,
    }


@router.get("/briefs/{brief_id}/cite-pack")
def download_cite_pack(
    brief_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    brief = db.get(Brief, brief_id)
    if brief is None or brief.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brief not found")
    run = db.get(Run, brief.run_id)
    payload = build_cite_pack(
        brief=brief.payload,
        raw_fire_weather=run.raw_fire_weather if run else None,
        raw_watchbox=run.raw_watchbox if run else None,
    )
    filename = f"emberline_{brief_id}_cite.zip"
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
