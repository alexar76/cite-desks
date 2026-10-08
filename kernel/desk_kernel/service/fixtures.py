from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from desk_kernel.claim import ClaimClass
from desk_kernel.hub import HubError

_PACKAGED = Path(__file__).resolve().parent / "fixtures"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture(claim: ClaimClass, fixture_dir: str, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    root = Path(fixture_dir) if fixture_dir else _PACKAGED / claim.id
    mapping = {
        claim.cheap_sku: "watchbox.json" if claim.cheap_sku else "",
        claim.brief_sku: "brief.json",
    }
    name = mapping.get(capability_id)
    if not name:
        raise HubError(f"unknown capability in fixture mode: {capability_id}")
    path = root / name
    if not path.is_file():
        raise HubError(f"missing fixture {path}")
    data = _load(path)
    if "bbox" in payload and isinstance(data, dict):
        data = {**data, "bbox": {k: payload.get(k) for k in ("west", "south", "east", "north") if payload.get(k) is not None}}
    if claim.watch_kind == "point" and isinstance(data, dict):
        data = {**data, "query": {"lat": payload.get("lat"), "lon": payload.get("lon")}}
    return data
