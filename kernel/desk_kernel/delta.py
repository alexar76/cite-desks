from __future__ import annotations

from typing import Any

from .claim import ClaimClass

MATERIAL = 5.0


def _item_key(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if ident:
        return f"id:{ident}"
    lat = round(float(item.get("lat") or 0.0), 4)
    lon = round(float(item.get("lon") or 0.0), 4)
    return f"ll:{lat:.4f},{lon:.4f}"


def _card(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "lat": item.get("lat"),
        "lon": item.get("lon"),
        "label": item.get("label") or item.get("headline") or item.get("name"),
        "source": item.get("source"),
        "kind": item.get("kind") or item.get("claim_class"),
        "brightness_k": item.get("brightness_k"),
        "observed_at": item.get("observed_at") or item.get("issued_at"),
    }


def _items(brief: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        brief.get("items")
        or brief.get("hotspots")
        or brief.get("warnings")
        or brief.get("vessels")
        or []
    )


def _count(brief: dict[str, Any], field: str) -> int:
    try:
        return int(brief.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def first_run_delta(claim: ClaimClass) -> dict[str, Any]:
    return {
        "artifact_type": claim.delta_artifact_type,
        "kind": "first_run",
        "versus_brief_id": None,
        "versus_run_id": None,
        "versus_generated_at": None,
        "summary": "No prior completed brief on this watch. Comparison starts on the next run.",
        "live_count": None,
        "evidence_status": None,
        "appeared": [],
        "disappeared": [],
        "changed": [],
        "unchanged_count": 0,
        "counts": {"appeared": 0, "disappeared": 0, "changed": 0, "unchanged": 0},
        "limitations": [
            f"Delta compares two {claim.product_name} briefs on the same watch. It is not a forecast or a risk score.",
            "A disappeared item may be a coverage gap — not that the event ended.",
        ],
    }


def compare_briefs(
    claim: ClaimClass,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    if previous is None:
        return first_run_delta(claim)

    now = _items(current)
    then = _items(previous)
    now_map = {_item_key(item): item for item in now}
    then_map = {_item_key(item): item for item in then}

    appeared = [_card(now_map[key]) for key in now_map.keys() - then_map.keys()]
    disappeared = [_card(then_map[key]) for key in then_map.keys() - now_map.keys()]
    unchanged = len(now_map.keys() & then_map.keys())
    live_from = _count(previous, claim.count_field)
    live_to = _count(current, claim.count_field)
    status_from = previous.get("evidence_status")
    status_to = current.get("evidence_status")
    parts = [f"LIVE count {live_from} -> {live_to} ({live_to - live_from:+d})."]
    if status_from != status_to:
        parts.append(f"Evidence {status_from} -> {status_to}.")
    parts.append(f"{len(appeared)} appeared, {len(disappeared)} disappeared.")
    return {
        "artifact_type": claim.delta_artifact_type,
        "kind": "versus_prior",
        "versus_brief_id": previous.get("id"),
        "versus_run_id": previous.get("run_id"),
        "versus_generated_at": previous.get("generated_at"),
        "summary": " ".join(parts),
        "live_count": {"from": live_from, "to": live_to, "delta": live_to - live_from},
        "evidence_status": {"from": status_from, "to": status_to},
        "appeared": appeared,
        "disappeared": disappeared,
        "changed": [],
        "unchanged_count": unchanged,
        "counts": {
            "appeared": len(appeared),
            "disappeared": len(disappeared),
            "changed": 0,
            "unchanged": unchanged,
        },
        "limitations": [
            f"Delta compares two {claim.product_name} briefs on the same watch. It is not a forecast or a risk score.",
            "A disappeared item may be a coverage gap — not that the event ended.",
        ],
    }
