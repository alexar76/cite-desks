from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class BBoxError(ValueError):
    pass


class PointError(ValueError):
    pass


def validate_bbox(
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    max_span_ew: float = 40.0,
    max_span_ns: float = 30.0,
) -> dict[str, float]:
    if not (-180.0 <= west < east <= 180.0):
        raise BBoxError("west/east must satisfy -180 <= west < east <= 180")
    if not (-90.0 <= south < north <= 90.0):
        raise BBoxError("south/north must satisfy -90 <= south < north <= 90")
    if (east - west) > max_span_ew or (north - south) > max_span_ns:
        raise BBoxError(
            f"bbox is too large for an evidence watch (max {max_span_ew:g}° × {max_span_ns:g}°)"
        )
    return {
        "west": round(float(west), 6),
        "south": round(float(south), 6),
        "east": round(float(east), 6),
        "north": round(float(north), 6),
    }


def validate_point(lat: float, lon: float) -> dict[str, float]:
    if not (-90.0 <= float(lat) <= 90.0):
        raise PointError("lat must satisfy -90 <= lat <= 90")
    if not (-180.0 <= float(lon) <= 180.0):
        raise PointError("lon must satisfy -180 <= lon <= 180")
    return {"lat": round(float(lat), 6), "lon": round(float(lon), 6)}


def point_in_bbox(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    return bbox["south"] <= lat <= bbox["north"] and bbox["west"] <= lon <= bbox["east"]


def bbox_intersects(
    bbox: dict[str, float],
    west: float,
    south: float,
    east: float,
    north: float,
) -> bool:
    return not (
        bbox["east"] < west or bbox["west"] > east or bbox["north"] < south or bbox["south"] > north
    )


# Rough licensed envelopes — used to refuse a Seamark box drawn over the wrong sea.
FINNISH_WATERS = {"west": 19.0, "south": 59.5, "east": 30.5, "north": 66.2}
NORWEGIAN_WATERS = {"west": 4.0, "south": 57.8, "east": 31.5, "north": 71.4}
# Split the overlapping rectangular envelopes for source selection.  Southern
# Norway is west of 19E; the Norwegian coast reaches east of 19E only in the
# far north, above the Finnish service box.
NORWEGIAN_MAIN_WATERS = {"west": 4.0, "south": 57.8, "east": 19.0, "north": 71.4}
NORWEGIAN_NORTH_WATERS = {"west": 19.0, "south": 66.2, "east": 31.5, "north": 71.4}


def nordic_ais_device_ids(bbox: dict[str, float]) -> tuple[str, ...]:
    """Return the licensed public AIS relays whose service area intersects bbox."""
    device_ids: list[str] = []
    if bbox_intersects(bbox, **FINNISH_WATERS):
        device_ids.append("fintraffic-ais-01")
    if bbox_intersects(bbox, **NORWEGIAN_MAIN_WATERS) or bbox_intersects(
        bbox, **NORWEGIAN_NORTH_WATERS
    ):
        device_ids.append("kystverket-ais-01")
    return tuple(device_ids)


def nordic_ais_ok(bbox: dict[str, float]) -> bool:
    return bool(nordic_ais_device_ids(bbox))


def in_quiet_hours(quiet: str, tz_name: str, now: datetime | None = None) -> bool:
    raw = (quiet or "").strip()
    if not raw or "-" not in raw:
        return False
    start_s, end_s = raw.split("-", 1)
    try:
        start_h = int(start_s)
        end_h = int(end_s)
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except (ValueError, ZoneInfoNotFoundError):
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    hour = current.astimezone(tz).hour
    if start_h == end_h:
        return False
    if start_h < end_h:
        return start_h <= hour < end_h
    return hour >= start_h or hour < end_h


def parse_schedule(schedule: str, allowed: tuple[str, ...] = ("15m", "30m", "60m")) -> str:
    if schedule in allowed:
        return schedule
    raise ValueError(f"schedule must be one of {', '.join(allowed)}")


def interval_minutes(schedule: str) -> int:
    return {"15m": 15, "30m": 30, "60m": 60, "12h": 720, "1d": 1440}.get(schedule, 60)


def is_live_item(item: dict[str, Any]) -> bool:
    if not item.get("live"):
        return False
    mode = str(item.get("mode") or "").lower()
    return mode != "sim"
