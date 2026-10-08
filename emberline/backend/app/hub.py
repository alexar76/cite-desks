from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from desk_kernel.supply import note_supply_credit

from .briefs import SKU_FIRE, SKU_WATCHBOX
from .config import get_settings

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class HubError(RuntimeError):
    pass


def _load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURE_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_fire_weather(bbox: dict[str, float] | None = None) -> dict[str, Any]:
    payload = _load_fixture("fire_weather_live.json")
    if bbox:
        payload = {**payload, "bbox": bbox}
    return payload


def fixture_watchbox(*, live_match_count: int) -> dict[str, Any]:
    name = "watchbox_match.json" if live_match_count > 0 else "watchbox_empty.json"
    return _load_fixture(name)


class HubClient:
    """Pays AIMarket Hub for ATLAS SKUs, or replays signed fixtures in demo mode."""

    def __init__(self, mode: str | None = None) -> None:
        settings = get_settings()
        self.mode = (mode or settings.hub_mode).lower()
        self.base = settings.hub_url.rstrip("/")
        self.api_key = settings.hub_api_key
        self.payment_channel = settings.hub_payment_channel.strip()
        self.payment_channel_secret = settings.hub_payment_channel_secret.strip()
        self.visitor = settings.hub_sandbox_visitor

    def invoke(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.mode != "live":
            return self._fixture_invoke(capability_id, payload)
        if bool(self.payment_channel) != bool(self.payment_channel_secret):
            raise HubError(
                "HUB_PAYMENT_CHANNEL and HUB_PAYMENT_CHANNEL_SECRET must be set together"
            )
        if not self.api_key and not self.payment_channel:
            raise HubError(
                "HUB_API_KEY or HUB_PAYMENT_CHANNEL credentials required when HUB_MODE=live"
            )
        headers = {
            "Content-Type": "application/json",
        }
        if self.payment_channel:
            headers["X-Payment-Channel"] = self.payment_channel
            headers["X-Payment-Channel-Secret"] = self.payment_channel_secret
        else:
            headers["X-API-Key"] = self.api_key
        body = {
            "product_id": "atlas.products",
            "capability_id": capability_id,
            "input": payload,
        }
        if self.base != "https://atlas.modelmarket.dev":
            body["source_hub"] = "https://atlas.modelmarket.dev"
        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(f"{self.base}/ai-market/v2/invoke", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise HubError(f"hub unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise HubError(f"hub {response.status_code}: {response.text[:400]}")
        # Same reading as the kernel's client, from the same shared parser: the remaining
        # prepaid balance is the only warning before `supply_unpaid` fails a customer's run.
        note_supply_credit(response.headers, seller=self.base)
        try:
            data = response.json()
        except ValueError as exc:
            raise HubError(f"hub returned non-JSON success body: {response.text[:400]}") from exc
        if not isinstance(data, dict):
            raise HubError("hub returned a non-object JSON body")
        result = data.get("result") if "result" in data else data
        if not isinstance(result, dict):
            raise HubError("hub result was not a JSON object")
        result = dict(result)
        result["_hub_envelope"] = {
            "hub_url": self.base,
            "source_hub": body.get("source_hub") or self.base,
            "receipt": data.get("receipt"),
            "provenance_receipt": data.get("provenance_receipt"),
            "verification": data.get("verification"),
            "price_usd": data.get("price_usd"),
            "latency_ms": data.get("latency_ms"),
        }
        return result

    def fire_weather(self, bbox: dict[str, float], limit: int = 24) -> dict[str, Any]:
        return self.invoke(SKU_FIRE, {**bbox, "limit": limit})

    def watchbox_check(self, bbox: dict[str, float], layers: list[str] | None = None) -> dict[str, Any]:
        return self.invoke(
            SKU_WATCHBOX,
            {**bbox, "layers": layers or ["fire"]},
        )

    def _fixture_invoke(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        bbox = {
            "west": payload.get("west"),
            "south": payload.get("south"),
            "east": payload.get("east"),
            "north": payload.get("north"),
        }
        if capability_id == SKU_FIRE:
            return fixture_fire_weather(bbox)
        if capability_id == SKU_WATCHBOX:
            snapshot = fixture_fire_weather(bbox)
            live = int((snapshot.get("evidence") or {}).get("live_fire_detection_count") or 0)
            check = fixture_watchbox(live_match_count=live)
            return {**check, "bbox": bbox, "layers": payload.get("layers") or ["fire"]}
        if capability_id == "atlas.smoke.operations@v1":
            return {
                "ok": True,
                "capability_id": "atlas.smoke.operations@v1",
                "inside_smoke": False,
                "density": None,
                "limitations": [
                    "HMS qualitative North America polygon. Not measured PM2.5.",
                    "Not a fire perimeter or evacuation order.",
                ],
                "query": {"lat": payload.get("lat"), "lon": payload.get("lon")},
            }
        raise HubError(f"unknown capability in fixture mode: {capability_id}")
