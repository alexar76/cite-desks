from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from . import __version__
from . import basepay
from .config import assert_runtime_safety, get_settings
from .db import Base, SessionLocal, engine, ensure_schema
from .engine import EngineError, execute_watch
from .geo import interval_minutes
from .models import Watch
from .routers import archive, auth, basepay as basepay_router, billing, ops, pay, public, push, watches
from .seed import seed_demo

scheduler = BackgroundScheduler()
_tick_lock = threading.Lock()

log = logging.getLogger(__name__)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _advisory_lock(db) -> bool:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return True
    return bool(db.execute(text("SELECT pg_try_advisory_lock(87421001)")).scalar())


def _advisory_unlock(db) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    db.execute(text("SELECT pg_advisory_unlock(87421001)"))


def _tick() -> None:
    if not _tick_lock.acquire(blocking=False):
        return
    db = SessionLocal()
    locked = False
    try:
        locked = _advisory_lock(db)
        if not locked:
            return
        for watch in db.query(Watch).filter(Watch.status == "active").all():
            minutes = interval_minutes(watch.schedule)
            if watch.last_run_at is None:
                try:
                    execute_watch(db, watch)
                except EngineError:
                    continue
                continue
            age = (datetime.now(timezone.utc) - _aware(watch.last_run_at)).total_seconds() / 60
            if age >= minutes:
                try:
                    execute_watch(db, watch)
                except EngineError:
                    continue
    finally:
        if locked:
            try:
                _advisory_unlock(db)
            except Exception:
                pass
        db.close()
        _tick_lock.release()


_pay_lock = threading.Lock()


def _scan_base() -> None:
    if not basepay.rail_enabled():
        return
    if not _pay_lock.acquire(blocking=False):
        return
    db = SessionLocal()
    locked = False
    try:
        locked = _advisory_lock_pay(db)
        if not locked:
            return
        basepay.scan_payments(db)
    except Exception:
        # Was a bare `db.rollback()` with no log line. The payment scan is the only thing
        # that turns a customer's USDC into a desk key, so a poll that stops seeing
        # transfers must not be indistinguishable from a poll that saw none — that is how
        # a silently-too-wide eth_getLogs window went unnoticed.
        log.exception("basepay: scheduled payment scan failed; invoices stay unsettled")
        db.rollback()
    finally:
        if locked:
            try:
                _advisory_unlock_pay(db)
            except Exception:
                pass
        db.close()
        _pay_lock.release()


def _advisory_lock_pay(db) -> bool:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return True
    return bool(db.execute(text("SELECT pg_try_advisory_lock(87421002)")).scalar())


def _advisory_unlock_pay(db) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    db.execute(text("SELECT pg_advisory_unlock(87421002)"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    assert_runtime_safety(settings)
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    if settings.seed_demo:
        db = SessionLocal()
        try:
            seed_demo(db)
        finally:
            db.close()
    if settings.scheduler_enabled and settings.app_env != "test":
        if not settings.is_demo or settings.desk_demo_scheduler:
            scheduler.add_job(_tick, "interval", minutes=5, id="watch-tick", replace_existing=True)
        scheduler.add_job(
            _scan_base,
            "interval",
            seconds=basepay.PAY_SCAN_INTERVAL_SECONDS,
            id="base-pay-scan",
            replace_existing=True,
        )
        closed = basepay.rail_closed_reason(settings)
        if closed:
            # Loud: a desk with a closed rail sells nothing, and the only other symptom is
            # a 503 on the buyer's side.
            log.warning("basepay: settlement scan will find nothing to settle — %s", closed)
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Emberline",
        version=__version__,
        description="Fire Evidence Desk — citeable detections, not invented perimeters.",
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
        allow_headers=["Authorization", "Content-Type", "X-Emberline-Mint", "X-Emberline-Ops"],
    )
    app.include_router(public.router)
    app.include_router(auth.router)
    app.include_router(watches.router)
    app.include_router(archive.router)
    app.include_router(billing.router)
    app.include_router(pay.router)
    app.include_router(basepay_router.router)
    app.include_router(push.router)
    app.include_router(ops.router)
    return app


app = create_app()
