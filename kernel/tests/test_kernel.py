from __future__ import annotations

import io
import base64
import hashlib
import json
import os
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("HUB_MODE", "fixture")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_DEMO", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-must-be-at-least-32b")
os.environ.setdefault("PAY_MODE", "fixture")
os.environ.setdefault("DESK_MODE", "live")
os.environ.setdefault("DESK_ID", "tideline")

from desk_kernel.claim import EMBERLINE, PLINTH, SEAMARK, SOLRECORD, TIDELINE
from desk_kernel.citepack import build_cite_pack
from desk_kernel.geo import (
    BBoxError,
    nordic_ais_device_ids,
    nordic_ais_ok,
    validate_bbox,
    validate_point,
)
from desk_kernel.hmac import sign_webhook, verify_webhook
from desk_kernel.policy import should_buy_brief
from desk_kernel.briefs import build_brief, split_campus_lists, split_flood_lists
from desk_kernel.receipt import receipt_panel


def test_bbox_and_point() -> None:
    box = validate_bbox(-1.2, 51.2, 0.6, 51.7)
    assert box["west"] == -1.2
    try:
        validate_bbox(-114, 32, -125, 42)
        raise AssertionError("inverted bbox")
    except BBoxError:
        pass
    pt = validate_point(35.0, -117.5)
    assert pt["lat"] == 35.0


def test_hmac_roundtrip() -> None:
    body = b'{"event":"tideline.alert"}'
    header = sign_webhook("secret", body, ts=1_700_000_000)
    assert header.startswith("t=")
    assert verify_webhook("secret", body, header, max_age_s=10**12)


def test_on_match_skips_empty() -> None:
    assert should_buy_brief(policy="always_brief", cheap_snapshot={"live_match_count": 0})
    assert not should_buy_brief(policy="on_match", cheap_snapshot={"evidence": {"live_match_count": 0}})
    assert should_buy_brief(policy="on_match", cheap_snapshot={"evidence": {"live_match_count": 2}})


def test_flood_split_never_one_score() -> None:
    warnings, gauges = split_flood_lists(
        [
            {"id": "w", "kind": "flood_warning", "headline": "Flood warning", "live": True, "mode": "live", "lat": 51.4, "lon": -0.3},
            {"id": "g", "kind": "river_gauge", "headline": "stage", "live": True, "mode": "live", "lat": 51.4, "lon": -0.3},
        ]
    )
    assert len(warnings) == 1 and warnings[0]["claim_class"] == "warning_product"
    assert len(gauges) == 1 and gauges[0]["claim_class"] == "in_situ_gauge"


def test_campus_split_never_one_score() -> None:
    weather, air, warnings, gauges, grid = split_campus_lists(
        [
            {"id": "w", "kind": "weather", "headline": "nowcast", "live": True, "mode": "live"},
            {"id": "a", "kind": "air", "headline": "outdoor air", "live": True, "mode": "live"},
            {"id": "f", "kind": "flood_warning", "headline": "Flood warning", "live": True, "mode": "live"},
            {"id": "g", "kind": "river_gauge", "headline": "stage", "live": True, "mode": "live"},
            {"id": "e", "kind": "grid", "headline": "load", "live": True, "mode": "live"},
        ]
    )
    assert [row["claim_class"] for row in weather] == ["weather_nowcast"]
    assert [row["claim_class"] for row in air] == ["air_nowcast"]
    assert [row["claim_class"] for row in warnings] == ["warning_product"]
    assert [row["claim_class"] for row in gauges] == ["in_situ_gauge"]
    assert [row["claim_class"] for row in grid] == ["grid_reading"]


def test_plinth_brief_keeps_lists_apart() -> None:
    snapshot = {
        "ok": True,
        "summary": "campus brief",
        "items": [
            {"id": "w", "kind": "weather", "headline": "nowcast", "live": True, "mode": "live", "lat": 39.04, "lon": -77.45, "source": "Open-Meteo"},
            {"id": "a", "kind": "air", "headline": "outdoor air", "live": True, "mode": "live", "lat": 39.03, "lon": -77.46, "source": "public air"},
        ],
    }
    watch = {"id": "wat", "name": "Ashburn colo campus", "west": -77.52, "south": 39.0, "east": -77.38, "north": 39.08, "timezone": "America/New_York"}
    brief = build_brief(claim=PLINTH, watch=watch, snapshot=snapshot, run_id="run", brief_id="brf", skus_used=["atlas.situation.brief@v1"])
    assert brief["weather"] and brief["air"]
    assert brief["warnings"] == [] and brief["gauges"] == [] and brief["grid"] == []
    assert "campus risk score" in brief["claim_split"]
    assert "risk_score" not in brief
    assert brief["preset"] == "campus"


def test_tideline_brief_and_cite_pack() -> None:
    snapshot = {
        "ok": True,
        "summary": "two lists",
        "items": [
            {"id": "w", "kind": "flood", "headline": "warning product", "live": True, "mode": "live", "lat": 51.4, "lon": -0.3, "source": "EA flood"},
            {"id": "g", "kind": "river", "headline": "Kingston stage", "live": True, "mode": "live", "lat": 51.41, "lon": -0.3, "source": "EA Hydrology"},
        ],
        "receipt": {"digest": "x", "signature_status": "signed"},
    }
    brief = build_brief(
        claim=TIDELINE,
        watch={"id": "wat", "name": "Thames", "west": -1.2, "south": 51.2, "east": 0.6, "north": 51.7},
        snapshot=snapshot,
        run_id="run_1",
        brief_id="brf_1",
        skus_used=["atlas.situation.brief@v1"],
    )
    assert brief["warnings"] and brief["gauges"]
    assert "NOT A FLOOD MODEL" in brief["badges"]
    blob = build_cite_pack(claim=TIDELINE, brief=brief, raw={"primary": snapshot})
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = set(archive.namelist())
        assert "01-cover.pdf" in names
        assert "SHA256SUMS" in names
        assert "raw/primary.json" in names
    assert blob == build_cite_pack(claim=TIDELINE, brief=brief, raw={"primary": snapshot})


def test_tideline_accepts_real_atlas_situation_shape() -> None:
    snapshot = {
        "ok": True,
        "summary": "one warning and one gauge",
        "citations": [
            {"id": "w", "layer": "flood", "headline": "warning", "live": True, "mode": "live", "lat": 51.4, "lon": -0.3},
            {"id": "g", "layer": "river", "headline": "stage", "live": True, "mode": "live", "lat": 51.41, "lon": -0.3},
        ],
        "live_count": 2,
    }
    brief = build_brief(
        claim=TIDELINE,
        watch={"id": "wat", "name": "Thames", "west": -1.2, "south": 51.2, "east": 0.6, "north": 51.7},
        snapshot=snapshot,
        run_id="run_real",
        brief_id="brf_real",
        skus_used=["atlas.situation.brief@v1"],
    )
    assert brief["evidence_status"] == "live_evidence"
    assert len(brief["warnings"]) == 1
    assert len(brief["gauges"]) == 1


def test_seamark_accepts_real_gaia_reading_shape() -> None:
    snapshot = {
        "reading": {
            "device_id": "fintraffic-ais-01",
            "model": "GAIA-AIS (Fintraffic)",
            "ts": "2026-09-10T20:00:00Z",
            "attribution": "Fintraffic Digitraffic (CC BY 4.0)",
            "hotspots": [{"mmsi": "230123456", "latitude": 60.15, "longitude": 24.95}],
        },
        "attestation": {"algorithm": "ed25519", "value": "signed"},
    }
    brief = build_brief(
        claim=SEAMARK,
        watch={"id": "wat", "name": "Helsinki", "west": 24.4, "south": 59.8, "east": 25.4, "north": 60.4},
        snapshot=snapshot,
        run_id="run_ais",
        brief_id="brf_ais",
        skus_used=["gaia.ais.public.read@v1"],
    )
    assert brief["evidence_status"] == "live_evidence"
    assert brief["live_vessel_count"] == 1
    assert brief["finnish_ais"][0]["id"] == "230123456"


def _signed_gaia_source(
    private: Ed25519PrivateKey,
    *,
    device_id: str,
    model: str,
    mmsi: str,
    lat: float,
    lon: float,
) -> dict:
    reading = {
        "device_id": device_id,
        "model": model,
        "seq": 7,
        "ts": "2026-09-10T20:00:00Z",
        "values": {},
        "attribution": model,
        "hotspots": [{"mmsi": mmsi, "latitude": lat, "longitude": lon}],
    }
    values_hash = hashlib.sha256(b"{}").hexdigest()
    hotspots_hash = hashlib.sha256(
        json.dumps(
            reading["hotspots"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    canonical = (
        f"device:{device_id}|model:{model}|seq:7|ts:{reading['ts']}"
        f"|values_sha256:{values_hash}|hotspots_sha256:{hotspots_hash}"
    ).encode()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "reading": reading,
        "attestation": {
            "algorithm": "ed25519",
            "public_key": base64.b64encode(public).decode(),
            "value": base64.b64encode(private.sign(canonical)).decode(),
        },
        "_hub_envelope": {
            "source_hub": "https://iot.modelmarket.dev",
            "receipt": {"nonce": f"paid-{device_id}", "signature": {"value": "hub-signed"}},
        },
    }


def test_seamark_preserves_and_verifies_each_source_proof() -> None:
    private = Ed25519PrivateKey.generate()
    finnish = _signed_gaia_source(
        private,
        device_id="fintraffic-ais-01",
        model="Fintraffic Digitraffic",
        mmsi="230123456",
        lat=60.15,
        lon=24.95,
    )
    norwegian = _signed_gaia_source(
        private,
        device_id="kystverket-ais-01",
        model="Kystverket AIS",
        mmsi="257123456",
        lat=60.0,
        lon=10.5,
    )
    snapshot = {"ok": True, "readings": [finnish, norwegian]}
    brief = build_brief(
        claim=SEAMARK,
        watch={"id": "wat", "name": "Nordic", "west": 9.0, "south": 59.0, "east": 26.0, "north": 61.0},
        snapshot=snapshot,
        run_id="run_proofs",
        brief_id="brf_proofs",
        skus_used=["gaia.ais.public.read@v1", "gaia.ais.public.read@v1"],
    )
    assert len(brief["source_proofs"]) == 2
    assert all(proof["attestation_verified"] for proof in brief["source_proofs"])
    assert all(proof["identity_pinned"] is False for proof in brief["source_proofs"])
    assert brief["source_proofs"][0]["hub_envelope"]["receipt"]["nonce"].startswith("paid-")

    tampered = json.loads(json.dumps(snapshot))
    tampered["readings"][0]["reading"]["hotspots"][0]["latitude"] = 61.0
    bad = build_brief(
        claim=SEAMARK,
        watch={"id": "wat", "name": "Nordic", "west": 9.0, "south": 59.0, "east": 26.0, "north": 62.0},
        snapshot=tampered,
        run_id="run_tampered",
        brief_id="brf_tampered",
        skus_used=["gaia.ais.public.read@v1", "gaia.ais.public.read@v1"],
    )
    assert bad["source_proofs"][0]["attestation_verified"] is False
    assert bad["evidence_status"] == "no_live_evidence"
    assert any("GAIA source proof" in item for item in bad["limitations"])

    blob = build_cite_pack(claim=SEAMARK, brief=brief, raw={"primary": snapshot})
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        proofs = json.loads(archive.read("05-source-proofs.json"))
    assert [proof["device_id"] for proof in proofs] == [
        "fintraffic-ais-01",
        "kystverket-ais-01",
    ]


def test_seamark_upstream_match_outside_watch_is_not_live_evidence() -> None:
    source = _signed_gaia_source(
        Ed25519PrivateKey.generate(),
        device_id="fintraffic-ais-01",
        model="Fintraffic Digitraffic",
        mmsi="230999999",
        lat=65.0,
        lon=25.0,
    )
    snapshot = {
        "ok": True,
        "live_count": 1,
        "evidence": {"live_vessel_count": 1},
        "readings": [source],
    }
    brief = build_brief(
        claim=SEAMARK,
        watch={"id": "wat", "name": "Helsinki", "west": 24.4, "south": 59.8, "east": 25.4, "north": 60.4},
        snapshot=snapshot,
        run_id="run_outside",
        brief_id="brf_outside",
        skus_used=["gaia.ais.public.read@v1"],
    )
    assert brief["evidence_status"] == "no_live_evidence"
    assert brief["live_vessel_count"] == 0
    assert len(brief["source_proofs"]) == 1


def test_atlas_receipt_verifies_canonical_payload_and_detects_tamper() -> None:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    snapshot = {
        "ok": True,
        "summary": "signed body",
        "citations": [
            {
                "id": "w",
                "layer": "flood",
                "headline": "warning",
                "live": True,
                "mode": "live",
                "lat": 51.4,
                "lon": -0.3,
            }
        ],
    }
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    snapshot["receipt"] = {
        "algorithm": "sha256",
        "digest": hashlib.sha256(canonical).hexdigest(),
        "signature_status": "signed",
        "signature_b64": base64.b64encode(private.sign(canonical)).decode(),
        "public_key_b64": base64.b64encode(public).decode(),
    }
    panel = receipt_panel(snapshot, verified_key="atlas_verified")
    assert panel and panel["atlas_verified"] is True
    tampered = {**snapshot, "summary": "changed"}
    bad = receipt_panel(tampered, verified_key="atlas_verified")
    assert bad and bad["atlas_verified"] is False
    assert bad["verify_error"] == "payload digest did not match receipt"

    live_valid = {**snapshot, "_hub_envelope": {"source_hub": "https://atlas.modelmarket.dev"}}
    valid_brief = build_brief(
        claim=TIDELINE,
        watch={"id": "wat", "name": "Thames", "west": -1.2, "south": 51.2, "east": 0.6, "north": 51.7},
        snapshot=live_valid,
        run_id="run_good_receipt",
        brief_id="brf_good_receipt",
        skus_used=["atlas.situation.brief@v1"],
    )
    assert valid_brief["evidence_status"] == "live_evidence"

    live_tampered = {**tampered, "_hub_envelope": {"source_hub": "https://atlas.modelmarket.dev"}}
    brief = build_brief(
        claim=TIDELINE,
        watch={"id": "wat", "name": "Thames", "west": -1.2, "south": 51.2, "east": 0.6, "north": 51.7},
        snapshot=live_tampered,
        run_id="run_bad_receipt",
        brief_id="brf_bad_receipt",
        skus_used=["atlas.situation.brief@v1"],
    )
    assert brief["evidence_status"] == "no_live_evidence"
    assert any("receipt missing or invalid" in item for item in brief["limitations"])


def test_solrecord_and_seamark_claims() -> None:
    assert SOLRECORD.watch_kind == "point"
    assert "1d" in SOLRECORD.schedules
    assert SEAMARK.watch_kind == "bbox"
    assert nordic_ais_ok({"west": 24.4, "south": 59.8, "east": 25.4, "north": 60.4})
    assert not nordic_ais_ok({"west": -5.0, "south": 50.0, "east": 1.0, "north": 51.0})
    assert nordic_ais_device_ids(
        {"west": 24.4, "south": 59.8, "east": 25.4, "north": 60.4}
    ) == ("fintraffic-ais-01",)
    assert nordic_ais_device_ids(
        {"west": 9.8, "south": 58.8, "east": 11.2, "north": 60.1}
    ) == ("kystverket-ais-01",)
    assert EMBERLINE.extra_skus == ("atlas.smoke.operations@v1",)


def test_hub_invoke_body_routes_gaia_to_iot() -> None:
    from desk_kernel.hub import invoke_base, invoke_body

    gaia = invoke_body("gaia.ais.public.read@v1", {"west": 24.4, "south": 59.8, "east": 25.4, "north": 60.4})
    assert gaia["product_id"] == "gaia.gateway"
    assert gaia["source_hub"] == "https://iot.modelmarket.dev"
    atlas = invoke_body("atlas.pv.irradiance.record@v1", {"lat": 35.0, "lon": -117.5})
    assert atlas["product_id"] == "atlas.products"
    assert atlas["source_hub"] == "https://atlas.modelmarket.dev"
    direct_gaia = invoke_body(
        "gaia.ais.public.read@v1", {}, hub_url="https://iot.modelmarket.dev"
    )
    assert "source_hub" not in direct_gaia
    assert invoke_base("https://modelmarket.dev", "gaia.ais.public.read@v1") == "https://modelmarket.dev"
    assert invoke_base("https://atlas.modelmarket.dev", "atlas.watchbox.check@v1") == "https://atlas.modelmarket.dev"


def test_seamark_snapshot_routes_both_relays_and_keeps_partial_evidence() -> None:
    from desk_kernel.hub import HubError
    from desk_kernel.service.engine import _seamark_snapshot

    class Client:
        calls: list[str] = []

        def invoke(self, _capability_id: str, payload: dict) -> dict:
            device_id = payload["device_id"]
            self.calls.append(device_id)
            if device_id == "kystverket-ais-01":
                raise HubError("upstream timeout")
            return {"reading": {"device_id": device_id}, "attestation": {"value": "signed"}}

    client = Client()
    snapshot, source_count = _seamark_snapshot(
        client,
        {"west": 18.9, "south": 60.0, "east": 19.1, "north": 60.2},
    )
    assert client.calls == ["fintraffic-ais-01", "kystverket-ais-01"]
    assert source_count == 1
    assert snapshot["readings"][0]["reading"]["device_id"] == "fintraffic-ais-01"
    assert snapshot["limitations"] == ["kystverket-ais-01: upstream timeout"]


def test_live_hub_client_preserves_paid_envelope(monkeypatch) -> None:
    from desk_kernel.hub import HubClient

    class Response:
        status_code = 200
        text = "ok"
        headers: dict[str, str] = {}

        @staticmethod
        def json() -> dict:
            return {
                "result": {"reading": {"device_id": "fintraffic-ais-01"}},
                "receipt": {"nonce": "paid-call"},
                "price_usd": 0.004,
                "latency_ms": 12,
            }

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        @staticmethod
        def post(url, *, json, headers) -> Response:
            assert url == "https://modelmarket.dev/ai-market/v2/invoke"
            assert headers["X-API-Key"] == "secret"
            assert "Authorization" not in headers
            assert json["source_hub"] == "https://iot.modelmarket.dev"
            return Response()

    monkeypatch.setattr("desk_kernel.hub.httpx.Client", Client)
    client = HubClient(claim=SEAMARK, mode="live", api_key="secret")
    result = client.invoke("gaia.ais.public.read@v1", {"device_id": "fintraffic-ais-01"})
    assert result["_hub_envelope"]["source_hub"] == "https://iot.modelmarket.dev"
    assert result["_hub_envelope"]["receipt"]["nonce"] == "paid-call"
    assert result["_hub_envelope"]["price_usd"] == 0.004


def test_live_hub_client_unwraps_real_gaia_output_envelope(monkeypatch) -> None:
    from desk_kernel.hub import HubClient

    class Response:
        status_code = 200
        text = "ok"
        headers: dict[str, str] = {}

        @staticmethod
        def json() -> dict:
            return {
                "ok": True,
                "capability_id": "gaia.ais.public.read@v1",
                "output": {
                    "reading": {
                        "device_id": "fintraffic-ais-01",
                        "hotspots": [{"mmsi": "230123456"}],
                    },
                    "attestation": {"algorithm": "ed25519", "value": "signed"},
                },
                "receipt": {"nonce": "gaia-paid-call"},
                "provenance": {"source": "gaia.gateway"},
                "price_usd": 0.001,
            }

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        @staticmethod
        def post(*_args, **_kwargs) -> Response:
            return Response()

    monkeypatch.setattr("desk_kernel.hub.httpx.Client", Client)
    client = HubClient(claim=SEAMARK, mode="live", api_key="secret")
    result = client.invoke("gaia.ais.public.read@v1", {"device_id": "fintraffic-ais-01"})
    assert result["reading"]["device_id"] == "fintraffic-ais-01"
    assert result["_hub_envelope"]["receipt"]["nonce"] == "gaia-paid-call"
    assert result["_hub_envelope"]["provenance"]["source"] == "gaia.gateway"


def test_live_hub_client_uses_exactly_one_payment_rail(monkeypatch) -> None:
    from desk_kernel.hub import HubClient

    class Response:
        status_code = 200
        text = "ok"
        headers: dict[str, str] = {}

        @staticmethod
        def json() -> dict:
            return {"ok": True, "items": [], "receipt": {}}

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        @staticmethod
        def post(_url, *, json, headers) -> Response:
            assert json["source_hub"] == "https://atlas.modelmarket.dev"
            assert headers["X-Payment-Channel"] == "channel-1"
            assert headers["X-Payment-Channel-Secret"] == "channel-secret"
            assert "X-API-Key" not in headers
            assert "Authorization" not in headers
            return Response()

    monkeypatch.setattr("desk_kernel.hub.httpx.Client", Client)
    client = HubClient(
        claim=TIDELINE,
        mode="live",
        api_key="must-not-be-sent",
        payment_channel="channel-1",
        payment_channel_secret="channel-secret",
    )
    client.invoke("atlas.situation.brief@v1", {})


def _recording_client(monkeypatch, seen: list[dict]):
    """Capture where each purchase went and which credential paid for it."""

    class Response:
        status_code = 200
        text = "ok"
        headers: dict[str, str] = {}

        @staticmethod
        def json() -> dict:
            return {"ok": True, "reading": {}, "receipt": {}}

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        @staticmethod
        def post(url, *, json, headers) -> Response:
            seen.append({"url": url, "body": json, "headers": dict(headers)})
            return Response()

    monkeypatch.setattr("desk_kernel.hub.httpx.Client", Client)


def test_a_desk_buys_each_sku_from_whoever_actually_sells_it(monkeypatch) -> None:
    """ATLAS does not sell `gaia.*` — it answers 404, and seamark's every run failed on it.

    Buying ATLAS products straight from ATLAS is what makes a prepaid account work, so the
    fix is a second seller for the sensor relays, not routing everything back through a hub.
    """
    from desk_kernel.hub import HubClient

    seen: list[dict] = []
    _recording_client(monkeypatch, seen)
    client = HubClient(
        claim=SEAMARK,
        mode="live",
        hub_url="https://atlas.modelmarket.dev",
        api_key="atls_desk_key",
        gaia_hub_url="https://modelmarket.dev",
        gaia_hub_api_key="aimk_desk_key",
    )

    client.invoke("atlas.watchbox.check@v1", {})
    client.invoke("gaia.ais.public.read@v1", {"device_id": "fintraffic-ais-01"})

    atlas_call, gaia_call = seen
    assert atlas_call["url"].startswith("https://atlas.modelmarket.dev/")
    assert atlas_call["headers"]["X-API-Key"] == "atls_desk_key"
    assert "source_hub" not in atlas_call["body"], "already at the seller"

    assert gaia_call["url"].startswith("https://modelmarket.dev/")
    assert gaia_call["headers"]["X-API-Key"] == "aimk_desk_key"
    assert gaia_call["body"]["source_hub"] == "https://iot.modelmarket.dev"
    assert gaia_call["body"]["product_id"] == "gaia.gateway"


def test_a_desk_with_one_seller_is_unchanged(monkeypatch) -> None:
    """No second upstream configured must mean exactly the old behaviour."""
    from desk_kernel.hub import HubClient

    seen: list[dict] = []
    _recording_client(monkeypatch, seen)
    client = HubClient(
        claim=SEAMARK, mode="live", hub_url="https://modelmarket.dev", api_key="aimk_only"
    )

    client.invoke("gaia.ais.public.read@v1", {})

    assert seen[0]["url"].startswith("https://modelmarket.dev/")
    assert seen[0]["headers"]["X-API-Key"] == "aimk_only"


def test_a_payment_channel_is_never_sent_to_the_other_seller(monkeypatch) -> None:
    """A channel is issued by one hub; presenting it elsewhere leaks a live secret."""
    from desk_kernel.hub import HubClient

    seen: list[dict] = []
    _recording_client(monkeypatch, seen)
    client = HubClient(
        claim=SEAMARK,
        mode="live",
        hub_url="https://atlas.modelmarket.dev",
        payment_channel="channel-1",
        payment_channel_secret="channel-secret",
        gaia_hub_url="https://modelmarket.dev",
        gaia_hub_api_key="aimk_desk_key",
    )

    client.invoke("gaia.ais.public.read@v1", {})

    headers = seen[0]["headers"]
    assert "X-Payment-Channel" not in headers and "X-Payment-Channel-Secret" not in headers
    assert headers["X-API-Key"] == "aimk_desk_key"


def test_a_second_seller_without_a_key_refuses_instead_of_going_anonymous(monkeypatch) -> None:
    """Half-configured must fail loudly, not quietly land on a five-an-hour allowance."""
    import pytest

    from desk_kernel.hub import HubClient, HubError

    _recording_client(monkeypatch, [])
    client = HubClient(
        claim=SEAMARK,
        mode="live",
        hub_url="https://atlas.modelmarket.dev",
        api_key="atls_desk_key",
        gaia_hub_url="https://modelmarket.dev",
    )

    with pytest.raises(HubError, match="GAIA_HUB_API_KEY"):
        client.invoke("gaia.ais.public.read@v1", {})


def test_live_hub_client_rejects_non_json_success(monkeypatch) -> None:
    from desk_kernel.hub import HubClient, HubError

    class Response:
        status_code = 200
        text = "not-json"
        headers: dict[str, str] = {}

        @staticmethod
        def json() -> dict:
            raise ValueError("invalid JSON")

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        @staticmethod
        def post(*_args, **_kwargs) -> Response:
            return Response()

    monkeypatch.setattr("desk_kernel.hub.httpx.Client", Client)
    client = HubClient(claim=SEAMARK, mode="live", api_key="secret")
    try:
        client.invoke("gaia.ais.public.read@v1", {"device_id": "fintraffic-ais-01"})
        raise AssertionError("non-JSON success must fail closed")
    except HubError as exc:
        assert "non-JSON" in str(exc)


def test_hub_routing_metadata_does_not_break_the_content_receipt():
    """A routed LIVE result carries hub envelope keys the provider never signed.

    aimarket_hub stamps `routed_via`, `routing_fee_bps` (and sometimes `sandbox` /
    `verification`) into the result body on the federated path — the only path a desk
    uses to reach a peer capability. They were not excluded from the canonical payload,
    so every routed run failed verification and the integrity gate downgraded it to
    `no_live_evidence` with zero detections: the desk suppressed the evidence it sells.
    """
    import base64
    import hashlib

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from desk_kernel.receipt import _canonical_payload, verify_receipt

    body = {"ok": True, "summary": "two detections", "hotspots": [1, 2]}
    canonical = _canonical_payload(body)
    key = Ed25519PrivateKey.generate()
    receipt = {
        "algorithm": "sha256",
        "digest": hashlib.sha256(canonical).hexdigest(),
        "signature_alg": "ed25519",
        "public_key_b64": base64.b64encode(
            key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
        ).decode(),
        "signature_b64": base64.b64encode(key.sign(canonical)).decode(),
    }

    routed = dict(body)
    routed["receipt"] = receipt
    routed["_hub_envelope"] = {"hub_url": "https://modelmarket.dev"}
    routed["routed_via"] = "https://modelmarket.dev"
    routed["routing_fee_bps"] = 250
    routed["verification"] = {"tier": "grounded"}
    routed["sandbox"] = {"mode": "assay"}
    assert verify_receipt(receipt, payload=routed)["desk_verified"] is True

    # The exclusion must not become a hole: real content changes still fail.
    tampered = dict(routed)
    tampered["hotspots"] = [1]
    assert verify_receipt(receipt, payload=tampered)["desk_verified"] is False
