from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class WatchIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    west: float
    south: float
    east: float
    north: float
    layers: list[str] = ["fire", "weather"]
    timezone: str = "America/Los_Angeles"
    schedule: str = "60m"
    quiet_hours: str = ""
    status: str = "active"
    policy: str = "on_match"
    alert_live_hotspots: int = 1
    alert_brightness_k: float = 0.0
    slack_webhook: str = ""
    email_to: str = ""
    https_webhook: str = ""


class WatchOut(BaseModel):
    id: str
    name: str
    west: float
    south: float
    east: float
    north: float
    layers: list
    timezone: str
    schedule: str
    quiet_hours: str
    status: str
    policy: str
    alert_live_hotspots: int
    alert_brightness_k: float
    slack_webhook: str = ""
    email_to: str = ""
    https_webhook: str = ""
    has_webhook_secret: bool = False
    last_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchCreated(WatchOut):
    webhook_secret: str


class RunOut(BaseModel):
    id: str
    watch_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    evidence_status: str
    skus_used: list
    cogs_usd: float
    alerted: bool
    brief_id: str | None = None

    model_config = {"from_attributes": True}
