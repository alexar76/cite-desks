from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from desk_kernel.receipt import verify_receipt as _verify_receipt

from .delta import compare_briefs
from .geo import is_live_hotspot
from .plans import HUB_COGS

SKU_FIRE = "atlas.fire.weather@v1"
SKU_WATCHBOX = "atlas.watchbox.check@v1"

BADGES = (
    "NOT A PERIMETER",
    "NOT A FORECAST",
    "NOT AN EVACUATION ORDER",
)

SKU_SMOKE = "atlas.smoke.operations@v1"

EMBERLINE_LIMITATIONS = [
    "Emberline is a monitoring aid. It is not an emergency service, evacuation authority, or insurer.",
    "Absence of an alert is not a safety guarantee. Satellite revisit, cloud cover, and sensor gaps exist.",
    "Detections are thermal anomalies. Emberline does not invent fire perimeters, forecasts, or risk scores.",
    "HMS smoke, if requested on the watch, is a qualitative North America polygon — not measured PM2.5 and not a fire perimeter.",
    "Powered by AIMarket ATLAS/GAIA. Emberline does not operate satellites.",
]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_hotspot(raw: dict[str, Any]) -> dict[str, Any]:
    values = raw.get("values") if isinstance(raw.get("values"), dict) else {}
    return {
        "id": raw.get("id"),
        "lat": _num(raw.get("lat") if raw.get("lat") is not None else values.get("latitude")),
        "lon": _num(raw.get("lon") if raw.get("lon") is not None else values.get("longitude")),
        "brightness_k": _num(values.get("brightness_k") if values.get("brightness_k") is not None else raw.get("brightness_k")),
        "confidence": _num(values.get("confidence") if values.get("confidence") is not None else raw.get("confidence")),
        "satellite": raw.get("satellite"),
        "frp_mw": _num(raw.get("frp_mw"), default=0.0) or None,
        "observed_at": raw.get("observed_at"),
        "source": raw.get("source"),
        "live": True,
        "mode": "live",
    }


def live_hotspots(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [normalize_hotspot(h) for h in (snapshot.get("hotspots") or []) if is_live_hotspot(h)]


def evidence_status(snapshot: dict[str, Any]) -> str:
    evidence = snapshot.get("evidence") if isinstance(snapshot.get("evidence"), dict) else {}
    live_count = int(evidence.get("live_fire_detection_count") or 0)
    if live_count <= 0 and not live_hotspots(snapshot):
        return "no_live_evidence"
    return "live_evidence"


def weather_block(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    weather = snapshot.get("weather")
    if not isinstance(weather, dict) or not weather.get("live"):
        return None
    values = weather.get("values") if isinstance(weather.get("values"), dict) else {}
    return {
        "id": weather.get("id"),
        "place": weather.get("place"),
        "lat": weather.get("lat"),
        "lon": weather.get("lon"),
        "distance_km": snapshot.get("weather_distance_km"),
        "max_weather_km": snapshot.get("max_weather_km"),
        "temperature_c": values.get("temperature_c"),
        "humidity_pct": values.get("humidity_pct"),
        "pressure_hpa": values.get("pressure_hpa"),
        "source": weather.get("source"),
        "live": True,
        "mode": weather.get("mode") or "live",
    }


def verify_receipt(
    receipt: dict[str, Any], payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    return _verify_receipt(
        receipt, payload=payload, verified_key="emberline_verified"
    )


def receipt_panel(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    receipt = snapshot.get("receipt")
    if not isinstance(receipt, dict):
        return None
    checked = verify_receipt(receipt, snapshot)
    return {
        "algorithm": receipt.get("algorithm"),
        "digest": receipt.get("digest"),
        "service": receipt.get("service"),
        "capability_id": receipt.get("capability_id"),
        "signature_alg": receipt.get("signature_alg"),
        "signature_status": receipt.get("signature_status"),
        "ts": receipt.get("ts"),
        "public_key_b64": receipt.get("public_key_b64"),
        "signature_b64": receipt.get("signature_b64"),
        "emberline_verified": checked["emberline_verified"],
        "verify_error": checked["verify_error"],
    }


def sku_cogs(skus: list[str]) -> float:
    return round(sum(HUB_COGS.get(sku, 0.0) for sku in skus), 4)


def build_brief(
    *,
    watch: dict[str, Any],
    snapshot: dict[str, Any],
    run_id: str,
    brief_id: str,
    skus_used: list[str],
    generated_at: datetime | None = None,
    previous_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(timezone.utc)
    status = evidence_status(snapshot)
    receipt = receipt_panel(snapshot)
    integrity_limitations: list[str] = []
    if isinstance(snapshot.get("_hub_envelope"), dict) and (
        not receipt or receipt.get("emberline_verified") is not True
    ):
        status = "no_live_evidence"
        integrity_limitations.append(
            "LIVE ATLAS content receipt missing or invalid; fire claims suppressed."
        )
    hotspots = live_hotspots(snapshot) if status == "live_evidence" else []
    atlas_limits = [str(x) for x in (snapshot.get("limitations") or [])]
    brightest = max(hotspots, key=lambda h: h["brightness_k"], default=None)
    summary = snapshot.get("summary") if status == "live_evidence" else (
        "No LIVE thermal detections in this watch box on this run. "
        "Status is no_live_evidence. Emberline will not substitute SIM detections."
    )
    payload = {
        "id": brief_id,
        "run_id": run_id,
        "artifact_type": "emberline.evidence_brief@v1",
        "generated_at": generated.isoformat(),
        "watch": {
            "id": watch.get("id"),
            "name": watch.get("name"),
            "bbox": {
                "west": watch["west"],
                "south": watch["south"],
                "east": watch["east"],
                "north": watch["north"],
            },
            "timezone": watch.get("timezone"),
        },
        "skus_used": skus_used,
        "cogs_usd": sku_cogs(skus_used),
        "evidence_status": status,
        "summary": summary,
        "drivers": list(snapshot.get("drivers") or []) if status == "live_evidence" else [],
        "live_fire_detection_count": (
            int((snapshot.get("evidence") or {}).get("live_fire_detection_count") or len(hotspots))
            if status == "live_evidence"
            else 0
        ),
        "returned_detection_count": len(hotspots),
        "hotspots": hotspots,
        "brightest": brightest,
        "weather": weather_block(snapshot) if status == "live_evidence" else None,
        "limitations": atlas_limits + integrity_limitations + EMBERLINE_LIMITATIONS,
        "badges": list(BADGES),
        "receipt": receipt,
        "attribution": snapshot.get("attribution"),
        "legal_strip": (
            "Monitoring aid only. Not a perimeter, forecast, risk rating, evacuation order, "
            "or insurance product. Do not treat a quiet run as proof of safety."
        ),
    }
    payload["delta"] = compare_briefs(payload, previous_brief)
    return payload


def should_alert(brief: dict[str, Any], *, live_hotspots_threshold: int, brightness_k: float) -> bool:
    if brief.get("evidence_status") != "live_evidence":
        return False
    count = int(brief.get("live_fire_detection_count") or 0)
    if count < live_hotspots_threshold:
        return False
    if brightness_k > 0:
        brightest = brief.get("brightest") or {}
        if _num(brightest.get("brightness_k")) < brightness_k:
            return False
    return True
