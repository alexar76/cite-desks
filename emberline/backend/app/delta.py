from __future__ import annotations

from typing import Any

MATERIAL_BRIGHTNESS_K = 5.0

DELTA_LIMITATIONS = [
    "Delta compares two Emberline briefs on the same watch box. It is not a fire perimeter, spread model, growth rate, or containment claim.",
    "A disappeared point may be cloud, revisit gap, or sensor limit — not that a fire went out.",
    "An appeared point is a new LIVE thermal anomaly in this box on this run, not a confirmed ignition time.",
    "Brightness change is a Kelvin delta on matched detections, not intensity of an incident.",
]


def hotspot_key(hotspot: dict[str, Any]) -> str:
    ident = hotspot.get("id")
    if ident:
        return f"id:{ident}"
    lat = round(float(hotspot.get("lat") or 0.0), 4)
    lon = round(float(hotspot.get("lon") or 0.0), 4)
    return f"ll:{lat:.4f},{lon:.4f}"


def _card(hotspot: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": hotspot.get("id"),
        "lat": hotspot.get("lat"),
        "lon": hotspot.get("lon"),
        "brightness_k": hotspot.get("brightness_k"),
        "confidence": hotspot.get("confidence"),
        "satellite": hotspot.get("satellite"),
        "observed_at": hotspot.get("observed_at"),
    }


def _index(hotspots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in hotspots:
        out[hotspot_key(item)] = item
    return out


def _count(brief: dict[str, Any]) -> int:
    return int(brief.get("live_fire_detection_count") or 0)


def _sort_cards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("lat") or 0.0),
            float(row.get("lon") or 0.0),
            str(row.get("id") or ""),
        ),
    )


def _match_rule() -> dict[str, Any]:
    return {
        "primary": "hotspot.id",
        "fallback": "lat_lon_rounded_4dp",
        "material_brightness_k": MATERIAL_BRIGHTNESS_K,
    }


def first_run_delta() -> dict[str, Any]:
    return {
        "artifact_type": "emberline.run_delta@v1",
        "kind": "first_run",
        "versus_brief_id": None,
        "versus_run_id": None,
        "versus_generated_at": None,
        "summary": "No prior completed brief on this watch. Comparison starts on the next run.",
        "live_count": None,
        "evidence_status": None,
        "appeared": [],
        "disappeared": [],
        "brightened": [],
        "dimmed": [],
        "unchanged_count": 0,
        "counts": {
            "appeared": 0,
            "disappeared": 0,
            "brightened": 0,
            "dimmed": 0,
            "unchanged": 0,
        },
        "match": _match_rule(),
        "material_brightness_k": MATERIAL_BRIGHTNESS_K,
        "limitations": list(DELTA_LIMITATIONS),
    }


def compare_briefs(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if previous is None:
        return first_run_delta()

    now = list(current.get("hotspots") or [])
    then = list(previous.get("hotspots") or [])
    now_map = _index(now)
    then_map = _index(then)

    appeared = _sort_cards([_card(now_map[key]) for key in now_map.keys() - then_map.keys()])
    disappeared = _sort_cards([_card(then_map[key]) for key in then_map.keys() - now_map.keys()])
    brightened: list[dict[str, Any]] = []
    dimmed: list[dict[str, Any]] = []
    unchanged = 0
    for key in now_map.keys() & then_map.keys():
        before = float(then_map[key].get("brightness_k") or 0.0)
        after = float(now_map[key].get("brightness_k") or 0.0)
        delta_k = round(after - before, 2)
        row = {
            **_card(now_map[key]),
            "from_k": before,
            "to_k": after,
            "delta_k": delta_k,
        }
        if delta_k >= MATERIAL_BRIGHTNESS_K:
            brightened.append(row)
        elif delta_k <= -MATERIAL_BRIGHTNESS_K:
            dimmed.append(row)
        else:
            unchanged += 1

    live_from = _count(previous)
    live_to = _count(current)
    status_from = previous.get("evidence_status")
    status_to = current.get("evidence_status")
    parts = [f"LIVE detections {live_from} → {live_to} ({live_to - live_from:+d})."]
    if status_from != status_to:
        parts.append(f"Evidence {status_from} → {status_to}.")
    parts.append(
        f"{len(appeared)} appeared, {len(disappeared)} disappeared, "
        f"{len(brightened)} brightened and {len(dimmed)} dimmed by "
        f"≥{MATERIAL_BRIGHTNESS_K:g} K."
    )
    return {
        "artifact_type": "emberline.run_delta@v1",
        "kind": "versus_prior",
        "versus_brief_id": previous.get("id"),
        "versus_run_id": previous.get("run_id"),
        "versus_generated_at": previous.get("generated_at"),
        "summary": " ".join(parts),
        "live_count": {"from": live_from, "to": live_to, "delta": live_to - live_from},
        "evidence_status": {"from": status_from, "to": status_to},
        "appeared": appeared,
        "disappeared": disappeared,
        "brightened": _sort_cards(brightened),
        "dimmed": _sort_cards(dimmed),
        "unchanged_count": unchanged,
        "counts": {
            "appeared": len(appeared),
            "disappeared": len(disappeared),
            "brightened": len(brightened),
            "dimmed": len(dimmed),
            "unchanged": unchanged,
        },
        "match": _match_rule(),
        "material_brightness_k": MATERIAL_BRIGHTNESS_K,
        "limitations": list(DELTA_LIMITATIONS),
    }
