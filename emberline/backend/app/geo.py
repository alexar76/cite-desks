from __future__ import annotations

from desk_kernel.geo import BBoxError, in_quiet_hours, interval_minutes, point_in_bbox
from desk_kernel.geo import is_live_item as is_live_hotspot
from desk_kernel.geo import validate_bbox as _validate_bbox


def validate_bbox(west: float, south: float, east: float, north: float) -> dict[str, float]:
    return _validate_bbox(west, south, east, north, max_span_ew=40.0, max_span_ns=30.0)


def parse_cron_or_interval(schedule: str) -> str:
    allowed = {"15m", "30m", "60m"}
    if schedule in allowed:
        return schedule
    raise ValueError("schedule must be 15m, 30m, or 60m")


__all__ = [
    "BBoxError",
    "in_quiet_hours",
    "interval_minutes",
    "is_live_hotspot",
    "parse_cron_or_interval",
    "point_in_bbox",
    "validate_bbox",
]
