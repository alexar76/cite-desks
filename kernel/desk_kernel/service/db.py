from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    resolved = url or get_settings().database_url
    if resolved.startswith("sqlite"):
        kwargs: dict = {"future": True, "connect_args": {"check_same_thread": False}}
        if resolved in {"sqlite://", "sqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
        return create_engine(resolved, **kwargs)
    return create_engine(resolved, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine(url: str) -> None:
    global engine, SessionLocal
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
