from __future__ import annotations

from typing import Any

from .claim import ClaimClass
from .delta import compare_briefs
from .geo import is_live_item, point_in_bbox
from .receipt import receipt_panel, source_proofs


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _live_items(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = next(
        (
            value
            for key in ("items", "citations", "hotspots", "matches", "vessels", "warnings")
            if isinstance((value := snapshot.get(key)), list) and value
        ),
        [],
    )
    parent_reading: dict[str, Any] = {}
    if not rows and isinstance(snapshot.get("reading"), dict):
        parent_reading = snapshot["reading"]
        rows = parent_reading.get("hotspots") or []
    nested_snapshots = snapshot.get("readings")
    if not rows and isinstance(nested_snapshots, list):
        merged: list[dict[str, Any]] = []
        for entry in nested_snapshots:
            if not isinstance(entry, dict):
                continue
            merged.extend(_live_items(entry))
        return merged
    out: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        normalized = dict(raw)
        if parent_reading:
            # A gaia.*.read result is one signed LIVE-device reading. Its cluster
            # children intentionally do not repeat transport metadata.
            normalized.setdefault("live", True)
            normalized.setdefault("mode", "live")
            normalized.setdefault("source", parent_reading.get("attribution") or parent_reading.get("model"))
            normalized.setdefault("attribution", parent_reading.get("attribution"))
            normalized.setdefault("observed_at", parent_reading.get("ts"))
            normalized.setdefault("id", normalized.get("mmsi"))
            normalized.setdefault("kind", "ais")
        if not is_live_item(normalized):
            continue
        values = normalized.get("values") if isinstance(normalized.get("values"), dict) else {}
        out.append(
            {
                "id": normalized.get("id"),
                "lat": _num(normalized.get("lat") if normalized.get("lat") is not None else normalized.get("latitude") if normalized.get("latitude") is not None else values.get("latitude")),
                "lon": _num(normalized.get("lon") if normalized.get("lon") is not None else normalized.get("longitude") if normalized.get("longitude") is not None else values.get("longitude")),
                "kind": normalized.get("kind") or normalized.get("layer") or normalized.get("claim_class"),
                "headline": normalized.get("headline") or normalized.get("name") or normalized.get("label") or normalized.get("mmsi"),
                "source": normalized.get("source"),
                "attribution": normalized.get("attribution"),
                "observed_at": normalized.get("observed_at") or normalized.get("issued_at"),
                "brightness_k": _num(
                    values.get("brightness_k") if values.get("brightness_k") is not None else normalized.get("brightness_k")
                )
                or None,
                "live": True,
                "mode": "live",
            }
        )
    return out


def evidence_status(snapshot: dict[str, Any], items: list[dict[str, Any]]) -> str:
    if snapshot.get("ok") is False:
        return "no_live_evidence"
    evidence = snapshot.get("evidence") if isinstance(snapshot.get("evidence"), dict) else {}
    for key in (
        "live_match_count",
        "live_fire_detection_count",
        "live_warning_count",
        "live_vessel_count",
        "live_record_count",
    ):
        try:
            if int(evidence.get(key) or 0) > 0:
                return "live_evidence"
        except (TypeError, ValueError):
            continue
    if items:
        return "live_evidence"
    try:
        if int(snapshot.get("live_count") or 0) > 0:
            return "live_evidence"
    except (TypeError, ValueError):
        pass
    if snapshot.get("irradiance") or snapshot.get("record_kind"):
        return "live_evidence"
    return "no_live_evidence"


def split_flood_lists(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep warning products and in-situ gauges apart. Never one risk number."""
    warnings: list[dict[str, Any]] = []
    gauges: list[dict[str, Any]] = []
    for item in items:
        kind = str(item.get("kind") or item.get("layer") or "").lower()
        headline = str(item.get("headline") or "").lower()
        if "flood" in kind or "warning" in kind or "cap" in headline or "warning" in headline:
            warnings.append({**item, "claim_class": "warning_product"})
        elif "river" in kind or "gauge" in kind or "reservoir" in kind or "stage" in headline:
            gauges.append({**item, "claim_class": "in_situ_gauge"})
        elif "water" in kind or "wq" in kind:
            gauges.append({**item, "claim_class": "water_quality"})
        else:
            # Unknown stays in warnings only if the SKU said flood; otherwise gauge-side unknown.
            if "flood" in str(item.get("source") or "").lower():
                warnings.append({**item, "claim_class": "warning_product"})
            else:
                gauges.append({**item, "claim_class": "in_situ_or_other"})
    return warnings, gauges


def split_campus_lists(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Weather, air, flood warnings, river gauges, grid — never one campus risk score."""
    weather: list[dict[str, Any]] = []
    air: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    gauges: list[dict[str, Any]] = []
    grid: list[dict[str, Any]] = []
    for item in items:
        kind = str(item.get("kind") or item.get("layer") or "").lower()
        headline = str(item.get("headline") or "").lower()
        blob = f"{kind} {headline}"
        if "air" in blob:
            air.append({**item, "claim_class": "air_nowcast"})
        elif "flood" in blob or "warning" in blob or "cap" in blob or "alert" in blob:
            warnings.append({**item, "claim_class": "warning_product"})
        elif "river" in blob or "gauge" in blob or "stage" in blob:
            gauges.append({**item, "claim_class": "in_situ_gauge"})
        elif "grid" in blob or "energy" in blob:
            grid.append({**item, "claim_class": "grid_reading"})
        else:
            weather.append({**item, "claim_class": "weather_nowcast"})
    return weather, air, warnings, gauges, grid


def split_ais_lists(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fi: list[dict[str, Any]] = []
    no: list[dict[str, Any]] = []
    for item in items:
        blob = " ".join(
            str(item.get(k) or "") for k in ("source", "attribution", "headline", "kind")
        ).lower()
        if "kystverket" in blob or "barentswatch" in blob or "norway" in blob or "norsk" in blob:
            no.append({**item, "claim_class": "kystverket_ais"})
        else:
            fi.append({**item, "claim_class": "fintraffic_ais"})
    return fi, no


def build_brief(
    *,
    claim: ClaimClass,
    watch: dict[str, Any],
    snapshot: dict[str, Any],
    run_id: str,
    brief_id: str,
    skus_used: list[str],
    previous_brief: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    live_items = _live_items(snapshot)
    items = live_items if evidence_status(snapshot, live_items) == "live_evidence" else []
    receipt = receipt_panel(snapshot, verified_key=claim.verified_key)
    proofs = source_proofs(snapshot)
    live_transport = isinstance(snapshot.get("_hub_envelope"), dict) or any(
        isinstance(entry, dict) and isinstance(entry.get("_hub_envelope"), dict)
        for entry in (snapshot.get("readings") or [])
    )
    if claim.id == "seamark" and claim.watch_kind == "bbox":
        bbox = {
            "west": float(watch["west"]),
            "south": float(watch["south"]),
            "east": float(watch["east"]),
            "north": float(watch["north"]),
        }
        items = [
            item
            for item in items
            if point_in_bbox(float(item["lat"]), float(item["lon"]), bbox)
        ]
    # A relay can legitimately return vessels outside the customer's smaller
    # watchbox. Its upstream live_count must not turn that empty intersection
    # into a positive desk claim.
    status = (
        "live_evidence" if items else "no_live_evidence"
    ) if claim.id == "seamark" else evidence_status(snapshot, items)
    integrity_limitations: list[str] = []
    if live_transport and claim.id == "seamark":
        source_chain_ok = bool(proofs) and all(
            proof.get("attestation_verified") is True
            and isinstance((proof.get("hub_envelope") or {}).get("receipt"), dict)
            for proof in proofs
        )
        if not source_chain_ok:
            status = "no_live_evidence"
            integrity_limitations.append(
                "LIVE GAIA source proof missing or invalid; vessel claims suppressed."
            )
    elif live_transport and (
        not receipt or receipt.get(claim.verified_key) is not True
    ):
        status = "no_live_evidence"
        integrity_limitations.append(
            "LIVE ATLAS content receipt missing or invalid; evidence claims suppressed."
        )
    if status != "live_evidence":
        items = []
    atlas_limits = [str(x) for x in (snapshot.get("limitations") or [])]
    summary = snapshot.get("summary") if status == "live_evidence" else (
        f"No LIVE evidence in this watch on this run. Status is no_live_evidence. "
        f"{claim.product_name} will not substitute SIM detections."
    )
    watch_block: dict[str, Any] = {
        "id": watch.get("id"),
        "name": watch.get("name"),
        "timezone": watch.get("timezone"),
    }
    if claim.watch_kind == "point":
        watch_block["point"] = {"lat": watch.get("lat"), "lon": watch.get("lon")}
    else:
        watch_block["bbox"] = {
            "west": watch["west"],
            "south": watch["south"],
            "east": watch["east"],
            "north": watch["north"],
        }
    payload: dict[str, Any] = {
        "id": brief_id,
        "run_id": run_id,
        "artifact_type": claim.artifact_type,
        "desk": claim.id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "watch": watch_block,
        "skus_used": skus_used,
        "cogs_usd": claim.sku_cogs(skus_used),
        "evidence_status": status,
        "summary": summary,
        "drivers": list(snapshot.get("drivers") or []) if status == "live_evidence" else [],
        claim.count_field: len(items) if status == "live_evidence" else 0,
        "live_count": len(items) if status == "live_evidence" else 0,
        "items": items,
        "limitations": atlas_limits + integrity_limitations + list(claim.limitations),
        "badges": list(claim.badges),
        "receipt": receipt,
        "source_proofs": proofs,
        "attribution": snapshot.get("attribution"),
        "legal_strip": claim.legal_strip,
        "geography_note": claim.geography_note,
    }
    if claim.id == "tideline":
        warnings, gauges = split_flood_lists(items)
        payload["warnings"] = warnings
        payload["gauges"] = gauges
        payload["live_warning_count"] = len(warnings)
        payload["live_gauge_count"] = len(gauges)
        payload["items"] = warnings + gauges
        payload[claim.count_field] = len(warnings)
        payload["live_count"] = len(warnings) + len(gauges)
        payload["claim_split"] = "warning_product vs in_situ_gauge — never a single flood-risk number"
    elif claim.id == "seamark":
        fi, no = split_ais_lists(items)
        payload["finnish_ais"] = fi
        payload["norwegian_ais"] = no
        payload["live_vessel_count"] = len(fi) + len(no)
        payload["live_count"] = len(fi) + len(no)
        payload["claim_split"] = "Fintraffic vs Kystverket — never one Europe blob"
    elif claim.id == "solrecord":
        payload["irradiance"] = snapshot.get("irradiance") if status == "live_evidence" else None
        payload["aerosol"] = snapshot.get("aerosol") if status == "live_evidence" else None
        payload["record_kind"] = snapshot.get("record_kind")
        payload["live_record_count"] = 1 if status == "live_evidence" else 0
        payload["live_count"] = payload["live_record_count"]
    elif claim.id == "plinth":
        weather, air, warnings, gauges, grid = split_campus_lists(items)
        payload["weather"] = weather
        payload["air"] = air
        payload["warnings"] = warnings
        payload["gauges"] = gauges
        payload["grid"] = grid
        payload["items"] = weather + air + warnings + gauges + grid
        payload["live_site_count"] = len(payload["items"])
        payload["live_count"] = len(payload["items"])
        payload[claim.count_field] = len(payload["items"])
        payload["preset"] = claim.brief_preset
        payload["claim_split"] = (
            "weather vs air vs warning vs gauge vs grid — never a campus risk score"
        )
    if extra:
        payload.update(extra)
    payload["delta"] = compare_briefs(claim, payload, previous_brief)
    return payload


def should_alert(brief: dict[str, Any], *, live_threshold: int = 1) -> bool:
    if brief.get("evidence_status") != "live_evidence":
        return False
    count = int(brief.get("live_count") or brief.get("live_fire_detection_count") or 0)
    return count >= live_threshold
