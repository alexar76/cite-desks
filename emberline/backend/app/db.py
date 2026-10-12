from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_url() -> str:
    return get_settings().database_url


def make_engine(url: str | None = None):
    resolved = url or _engine_url()
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


def ensure_schema() -> None:
    """Add columns create_all will not backfill on an existing volume."""
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            invoice_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(base_invoices)")).fetchall()}
            if invoice_cols and "payment_method" not in invoice_cols:
                conn.execute(text("ALTER TABLE base_invoices ADD COLUMN payment_method VARCHAR(32) DEFAULT 'usdc_base'"))
            ws_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(workspaces)")).fetchall()}
            if ws_cols and "plan_expires_at" not in ws_cols:
                conn.execute(text("ALTER TABLE workspaces ADD COLUMN plan_expires_at DATETIME"))
            brief_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(briefs)")).fetchall()}
            if brief_cols and "share_token" not in brief_cols:
                conn.execute(text("ALTER TABLE briefs ADD COLUMN share_token VARCHAR(80)"))
            if brief_cols:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_briefs_share_token ON briefs(share_token)"))
        elif engine.dialect.name == "postgresql":
            conn.execute(
                text(
                    "ALTER TABLE IF EXISTS base_invoices "
                    "ADD COLUMN IF NOT EXISTS payment_method VARCHAR(32) DEFAULT 'usdc_base'"
                )
            )
            conn.execute(
                text("ALTER TABLE IF EXISTS workspaces ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ")
            )
            conn.execute(text("ALTER TABLE IF EXISTS briefs ADD COLUMN IF NOT EXISTS share_token VARCHAR(80)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_briefs_share_token ON briefs(share_token)"))


def reset_engine(url: str) -> None:
    """Test helper: rebind the global session to an isolated database."""
    global engine, SessionLocal
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
