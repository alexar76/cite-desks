from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    plan: Mapped[str] = mapped_column(String(20), default="solo")
    billing_email: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    users: Mapped[list[User]] = relationship(back_populates="workspace")
    watches: Mapped[list[Watch]] = relationship(back_populates="workspace")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="users")


class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    west: Mapped[float] = mapped_column(Float)
    south: Mapped[float] = mapped_column(Float)
    east: Mapped[float] = mapped_column(Float)
    north: Mapped[float] = mapped_column(Float)
    layers: Mapped[list] = mapped_column(JSON, default=lambda: ["fire", "weather"])
    timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles")
    schedule: Mapped[str] = mapped_column(String(80), default="60m")
    quiet_hours: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    policy: Mapped[str] = mapped_column(String(20), default="on_match")
    alert_live_hotspots: Mapped[int] = mapped_column(Integer, default=1)
    alert_brightness_k: Mapped[float] = mapped_column(Float, default=0.0)
    slack_webhook: Mapped[str] = mapped_column(String(400), default="")
    email_to: Mapped[str] = mapped_column(String(200), default="")
    https_webhook: Mapped[str] = mapped_column(String(400), default="")
    webhook_secret: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="watches")
    runs: Mapped[list[Run]] = relationship(back_populates="watch")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watches.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    evidence_status: Mapped[str] = mapped_column(String(32), default="unknown")
    skus_used: Mapped[list] = mapped_column(JSON, default=list)
    cogs_usd: Mapped[float] = mapped_column(Float, default=0.0)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")
    raw_watchbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_fire_weather: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    watch: Mapped[Watch] = relationship(back_populates="runs")
    brief: Mapped[Brief | None] = relationship(back_populates="run", uselist=False)


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watches.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON)
    share_token: Mapped[str | None] = mapped_column(String(80), unique=True, index=True, nullable=True)

    run: Mapped[Run] = relationship(back_populates="brief")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    sku: Mapped[str] = mapped_column(String(80), default="")
    amount_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeskGrant(Base):
    __tablename__ = "desk_grants"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payment_ref: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20), default="solo")
    days: Mapped[int] = mapped_column(Integer, default=30)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BaseInvoice(Base):
    __tablename__ = "base_invoices"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan: Mapped[str] = mapped_column(String(20))
    payment_method: Mapped[str] = mapped_column(String(32), default="usdc_base")
    days: Mapped[int] = mapped_column(Integer, default=30)
    amount_raw: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    pay_to: Mapped[str] = mapped_column(String(42))
    tx_hash: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(42), nullable=True)
    block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desk_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PushDevice(Base):
    __tablename__ = "push_devices"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
