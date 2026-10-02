from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from .claim import ClaimClass
from .supply import note_supply_credit

FixtureLoader = Callable[[str, dict[str, Any]], dict[str, Any]]


class HubError(RuntimeError):
    pass


class HubClient:
    """Pays whoever actually sells each capability, or replays fixtures.

    A desk's SKUs do not all come from one seller. Buying ATLAS products straight from
    ATLAS is what makes a prepaid account possible, but ATLAS does not sell `gaia.*` — it
    answers `404 unknown capability` — so a desk pointed only at ATLAS silently stops being
    able to produce briefs that need a sensor relay. Measured on seamark: every run failed
    on `gaia.ais.public.read@v1` while its ATLAS balance sat untouched.
    """

    def __init__(
        self,
        *,
        claim: ClaimClass,
        mode: str = "fixture",
        hub_url: str = "https://modelmarket.dev",
        api_key: str = "",
        payment_channel: str = "",
        payment_channel_secret: str = "",
        gaia_hub_url: str = "",
        gaia_hub_api_key: str = "",
        fixture_loader: FixtureLoader | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.claim = claim
        self.mode = (mode or "fixture").lower()
        self.base = hub_url.rstrip("/")
        self.api_key = api_key
        self.payment_channel = payment_channel.strip()
        self.payment_channel_secret = payment_channel_secret.strip()
        self.gaia_base = gaia_hub_url.rstrip("/")
        self.gaia_api_key = gaia_hub_api_key.strip()
        self.fixture_loader = fixture_loader
        self.timeout = timeout

    def _seller_of(self, capability_id: str) -> tuple[str, str]:
        """The origin that sells this capability, and the key that pays it.

        Only `gaia.*` is routed away, and only when a second upstream is configured: a desk
        with one seller must keep behaving exactly as before, including its failures.
        """
        if capability_id.startswith("gaia.") and self.gaia_base:
            return self.gaia_base, self.gaia_api_key
        return self.base, self.api_key

    def invoke(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.mode != "live":
            if self.fixture_loader is None:
                raise HubError("fixture loader required when HUB_MODE is not live")
            return self.fixture_loader(capability_id, payload)
        if bool(self.payment_channel) != bool(self.payment_channel_secret):
            raise HubError(
                "HUB_PAYMENT_CHANNEL and HUB_PAYMENT_CHANNEL_SECRET must be set together"
            )
        if not self.api_key and not self.payment_channel:
            raise HubError(
                "HUB_API_KEY or HUB_PAYMENT_CHANNEL credentials required when HUB_MODE=live"
            )
        if self.gaia_base and not self.gaia_api_key:
            # Falling back to the anonymous allowance here is how a desk ends up rate-limited
            # in production while looking configured, so refuse instead.
            raise HubError("GAIA_HUB_URL requires GAIA_HUB_API_KEY")
        base, key = self._seller_of(capability_id)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self.claim.user_agent,
        }
        # Never send a central-Hub secret as Authorization to a provider origin.
        # A channel wins over credits so the Hub cannot ambiguously select a rail — but a
        # channel is issued by one hub, so it is only ever sent to the origin it came from.
        if self.payment_channel and base == self.base:
            headers["X-Payment-Channel"] = self.payment_channel
            headers["X-Payment-Channel-Secret"] = self.payment_channel_secret
        else:
            headers["X-API-Key"] = key
        body = invoke_body(capability_id, payload, hub_url=base)
        url = f"{invoke_base(base, capability_id)}/ai-market/v2/invoke"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise HubError(f"hub unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise HubError(f"hub {response.status_code}: {response.text[:400]}")
        # Before the body: a purchase that spent prepaid credit reports the remaining
        # balance in its headers, and that is the only warning an operator gets before
        # `supply_unpaid` starts failing customers' runs.
        note_supply_credit(response.headers, seller=base)
        try:
            data = response.json()
        except ValueError as exc:
            raise HubError(f"hub returned non-JSON success body: {response.text[:400]}") from exc
        if not isinstance(data, dict):
            raise HubError("hub returned a non-object JSON body")
        # The general Hub wraps work as `result`; oracle-core providers such as
        # GAIA use `output`. ATLAS returns its product object directly. Normalize
        # only the two explicit envelopes and leave a direct product untouched.
        result_key = "result" if "result" in data else (
            "output" if "output" in data and "capability_id" in data and "receipt" in data else ""
        )
        envelope = {
            "hub_url": base,
            "source_hub": body.get("source_hub") or base,
            "receipt": data.get("receipt"),
            "provenance": data.get("provenance"),
            "provenance_receipt": data.get("provenance_receipt"),
            "verification": data.get("verification"),
            "price_usd": data.get("price_usd"),
            "latency_ms": data.get("latency_ms"),
        }
        if result_key:
            result = data[result_key]
            if not isinstance(result, dict):
                raise HubError(f"hub {result_key} was not a JSON object")
            # Do not throw away the paid Hub proof while unwrapping the useful
            # result. For multi-source Seamark this envelope is preserved once per
            # GAIA relay in source_proofs and in the raw cite-pack payload.
            result = dict(result)
            result["_hub_envelope"] = envelope
            return result
        # ATLAS returns the product directly rather than wrapping it. Marking the
        # live transport lets build_brief require its content receipt, while the
        # injected metadata is excluded from ATLAS's pre-existing signed canonical.
        direct = dict(data)
        direct["_hub_envelope"] = envelope
        return direct


GAIA_HUB = "https://iot.modelmarket.dev"
ATLAS_HUB = "https://atlas.modelmarket.dev"


def invoke_base(hub_url: str, capability_id: str) -> str:
    """All paid work goes through the configured buyer Hub."""

    return hub_url.rstrip("/")


def invoke_body(
    capability_id: str,
    payload: dict[str, Any],
    *,
    hub_url: str = "https://modelmarket.dev",
) -> dict[str, Any]:
    """Name the provider explicitly when buying through a routing Hub."""

    body: dict[str, Any] = {"capability_id": capability_id, "input": payload}
    if capability_id.startswith("gaia."):
        body["product_id"] = "gaia.gateway"
        if hub_url.rstrip("/") != GAIA_HUB:
            body["source_hub"] = GAIA_HUB
    elif capability_id.startswith("atlas."):
        body["product_id"] = "atlas.products"
        if hub_url.rstrip("/") != ATLAS_HUB:
            body["source_hub"] = ATLAS_HUB
    return body
