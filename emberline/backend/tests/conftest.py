from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["HUB_MODE"] = "fixture"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO"] = "true"
os.environ["JWT_SECRET"] = "test-secret-must-be-at-least-32b"
os.environ["PAY_MINT_SECRET"] = "test-mint"
os.environ["PAY_MODE"] = "fixture"
os.environ.setdefault("DESK_MODE", "live")
os.environ["PAY_BASE_RPC_URL"] = "http://127.0.0.1:9"
os.environ["PAY_BASE_ADDRESS"] = "0x1111111111111111111111111111111111111111"
os.environ["LOGIN_RATE_LIMIT"] = "1000"

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.main import create_app
from app.payfixture import reset_fixture_rpc
from app.security import reset_rate_limits
from app.seed import seed_demo

get_settings.cache_clear()


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    reset_fixture_rpc()
    reset_rate_limits()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    seed_demo(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    with TestClient(create_app()) as test_client:
        yield test_client
