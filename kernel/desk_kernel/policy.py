from __future__ import annotations

from typing import Any


def live_match_count(snapshot: dict[str, Any]) -> int:
    if not isinstance(snapshot, dict):
        return 0
    evidence = snapshot.get("evidence") if isinstance(snapshot.get("evidence"), dict) else {}
    for key in (
        "live_match_count",
        "live_fire_detection_count",
        "live_warning_count",
        "live_vessel_count",
        "live_count",
    ):
        try:
            value = int(evidence.get(key) or snapshot.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if value:
            return value
    items = snapshot.get("matches") or snapshot.get("hotspots") or snapshot.get("items") or []
    return len(items) if isinstance(items, list) else 0


def should_buy_brief(*, policy: str, cheap_snapshot: dict[str, Any] | None) -> bool:
    """on_match buys the expensive SKU only when the cheap check saw LIVE hits."""
    if policy != "on_match":
        return True
    if cheap_snapshot is None:
        return True
    return live_match_count(cheap_snapshot) > 0
