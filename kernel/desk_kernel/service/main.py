from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from desk_kernel.claim import ClaimClass
from desk_kernel.service.api import router
from desk_kernel.service.config import assert_runtime_safety, current_claim, get_settings
from desk_kernel.service.db import Base, SessionLocal, engine
from desk_kernel.service.engine import due, execute_watch
from desk_kernel.service.models import Watch
from desk_kernel.service.pay import rail_closed_reason as pay_closed_reason
from desk_kernel.service.pay import rail_enabled, scan_payments
from desk_kernel.service.seed import seed_demo

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
_tick_lock = threading.Lock()
_pay_lock = threading.Lock()
#: A thread lock only orders the schedulers inside one process. Desks scale by adding API
#: containers against one database, and then two settlement scans read the same treasury
#: window at the same time. Postgres arbitrates; SQLite (dev/test) has one writer anyway.
WATCH_TICK_LOCK_ID = 87421001
PAY_SCAN_LOCK_ID = 87421002


def _advisory_lock(db, lock_id: int) -> bool:
    if db.get_bind().dialect.name != "postgresql":
        return True
    return bool(db.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar())


def _advisory_unlock(db, lock_id: int) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})


def _tick() -> None:
    if not _tick_lock.acquire(blocking=False):
        return
    db = SessionLocal()
    locked = False
    try:
        locked = _advisory_lock(db, WATCH_TICK_LOCK_ID)
        if not locked:
            return
        for watch in db.query(Watch).filter(Watch.status == "active").all():
            if due(watch):
                try:
                    execute_watch(db, watch)
                except Exception:
                    db.rollback()
    finally:
        if locked:
            try:
                _advisory_unlock(db, WATCH_TICK_LOCK_ID)
            except Exception:
                pass
        db.close()
        _tick_lock.release()


def _pay_tick() -> None:
    """The half of checkout that runs without anybody watching."""
    if not _pay_lock.acquire(blocking=False):
        return
    db = SessionLocal()
    locked = False
    try:
        locked = _advisory_lock(db, PAY_SCAN_LOCK_ID)
        if not locked:
            return
        scan_payments(db)
    except Exception:
        # Never a bare rollback: this poll is the only thing that turns a customer's USDC
        # into a desk key, so a scan that stops seeing transfers must not look like a scan
        # that saw none. That is how a silently-too-wide eth_getLogs window goes unnoticed
        # and a paying buyer waits forever.
        db.rollback()
        log.exception("pay: scheduled settlement scan failed; invoices stay unsettled")
    finally:
        if locked:
            try:
                _advisory_unlock(db, PAY_SCAN_LOCK_ID)
            except Exception:
                pass
        db.close()
        _pay_lock.release()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    claim = current_claim()
    assert_runtime_safety(settings, claim)
    Base.metadata.create_all(bind=engine)
    if settings.seed_demo:
        db = SessionLocal()
        try:
            seed_demo(db)
        finally:
            db.close()
    if settings.scheduler_enabled and settings.app_env != "test":
        if not settings.is_demo or settings.desk_demo_scheduler:
            scheduler.add_job(_tick, "interval", minutes=5, id="watch-tick", replace_existing=True)
        if rail_enabled(settings):
            scheduler.add_job(
                _pay_tick,
                "interval",
                seconds=max(5, int(settings.pay_scan_interval_seconds)),
                id="pay-scan",
                replace_existing=True,
            )
        else:
            # Loud, because a desk with a closed rail sells nothing and the symptom on the
            # buyer's side is a 503 with no trace in the log.
            log.warning("pay: settlement scan not scheduled — %s", pay_closed_reason(settings))
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


def create_app(desk_id: str | None = None) -> FastAPI:
    if desk_id:
        import os

        os.environ["DESK_ID"] = desk_id
        get_settings.cache_clear()
        current_claim.cache_clear()
    settings = get_settings()
    claim: ClaimClass = current_claim()
    app = FastAPI(
        title=claim.product_name,
        description=claim.tagline,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", claim.mint_header, claim.ops_header],
    )
    app.include_router(router)
    return app


def app_for(desk_id: str) -> FastAPI:
    return create_app(desk_id)


# Default: set DESK_ID in the environment. Sibling desks pin it in their entrypoint.
app = create_app()
