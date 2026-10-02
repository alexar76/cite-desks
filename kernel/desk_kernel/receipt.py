from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


#: Keys that are ENVELOPE, not content: the provider never signed them, so they must not
#: take part in the digest. `_hub_envelope` was already here; the rest are stamped into the
#: result body by the routing hub on the federated path (aimarket_hub/api.py: `routed_via`,
#: `routing_fee_bps`, `sandbox`, `verification`), which is the only path a desk uses to
#: reach a peer capability. Their absence meant every LIVE routed run failed verification,
#: and the integrity gate in build_brief turned that into `no_live_evidence` with zero
#: hotspots — the desk suppressed exactly the evidence it exists to sell.
_ENVELOPE_KEYS = (
    "receipt",
    "receipt_url",
    "verifier_url",
    "_hub_envelope",
    "routed_via",
    "routing_fee_bps",
    "sandbox",
    "verification",
    "provenance_receipt",
    "gateway_receipt",
)


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    body = {
        key: value
        for key, value in payload.items()
        if key not in _ENVELOPE_KEYS
    }
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def verify_receipt(
    receipt: dict[str, Any],
    *,
    payload: dict[str, Any] | None = None,
    verified_key: str = "desk_verified",
) -> dict[str, Any]:
    digest = str(receipt.get("digest") or "")
    sig_b64 = str(receipt.get("signature_b64") or "")
    key_b64 = str(receipt.get("public_key_b64") or "")
    if not digest or not sig_b64 or not key_b64:
        return {verified_key: False, "verify_error": "missing digest or signature material"}
    if payload is None:
        return {verified_key: False, "verify_error": "signed payload required for verification"}
    canonical = _canonical_payload(payload)
    computed = hashlib.sha256(canonical).hexdigest()
    if not hmac.compare_digest(computed, digest.lower()):
        return {verified_key: False, "verify_error": "payload digest did not match receipt"}
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64))
        signature = base64.b64decode(sig_b64)
    except (ValueError, binascii.Error) as exc:
        return {verified_key: False, "verify_error": f"malformed key or signature: {exc}"}
    try:
        # ATLAS signs the canonical response body; digest is a separately checked
        # content address, not the signed message.
        public.verify(signature, canonical)
    except InvalidSignature:
        return {
            verified_key: False,
            "verify_error": "ed25519 signature did not match canonical payload",
        }
    return {verified_key: True, "verify_error": None}


def receipt_panel(snapshot: dict[str, Any], *, verified_key: str = "desk_verified") -> dict[str, Any] | None:
    receipt = snapshot.get("receipt")
    if not isinstance(receipt, dict):
        return None
    checked = verify_receipt(receipt, payload=snapshot, verified_key=verified_key)
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
        verified_key: checked[verified_key],
        "verify_error": checked["verify_error"],
    }


def _gaia_reading_canonical(reading: dict[str, Any]) -> str:
    """Mirror GAIA's public device-attestation canonical.

    A self-carried device key proves that the reading and attestation stayed
    together without mutation. It does not, by itself, prove that the key is a
    registry-pinned GAIA device identity; callers must keep that distinction.
    """

    values_hash = hashlib.sha256(
        json.dumps(
            reading.get("values", {}),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    canonical = (
        f"device:{reading.get('device_id', '')}"
        f"|model:{reading.get('model', '')}"
        f"|seq:{reading.get('seq', 0)}"
        f"|ts:{reading.get('ts', '')}"
        f"|values_sha256:{values_hash}"
    )
    if isinstance(reading.get("hotspots"), list):
        hotspots_hash = hashlib.sha256(
            json.dumps(
                reading["hotspots"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        canonical += f"|hotspots_sha256:{hotspots_hash}"
    return canonical


def verify_gaia_attestation(reading: dict[str, Any], attestation: dict[str, Any]) -> bool:
    """Verify integrity against the public key carried by the GAIA reading."""

    if str(attestation.get("algorithm") or "").lower() != "ed25519":
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(str(attestation.get("public_key") or ""), validate=True)
        )
        signature = base64.b64decode(
            str(attestation.get("value") or ""), validate=True
        )
        public.verify(signature, _gaia_reading_canonical(reading).encode("utf-8"))
    except (InvalidSignature, TypeError, ValueError, binascii.Error):
        return False
    return True


def source_proofs(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract standalone proof bundles from one or more GAIA results.

    Seamark may buy both Nordic AIS relays. The normalized vessel list is useful
    for the brief, but it must not replace either signed source response.
    """

    nested = snapshot.get("readings")
    sources = nested if isinstance(nested, list) else [snapshot]
    proofs: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        reading = source.get("reading")
        attestation = source.get("attestation")
        hub_envelope = source.get("_hub_envelope")
        if not isinstance(reading, dict):
            continue
        proof: dict[str, Any] = {
            "source_index": index,
            "device_id": reading.get("device_id") if isinstance(reading, dict) else None,
            "model": reading.get("model") if isinstance(reading, dict) else None,
            "observed_at": reading.get("ts") if isinstance(reading, dict) else None,
            "reading": reading if isinstance(reading, dict) else None,
            "attestation": attestation if isinstance(attestation, dict) else None,
            "attestation_verified": bool(
                isinstance(reading, dict)
                and isinstance(attestation, dict)
                and verify_gaia_attestation(reading, attestation)
            ),
            "identity_pinned": False,
            "verification_scope": (
                "self-carried key verifies payload integrity; device identity is not registry-pinned by the desk"
            ),
        }
        if isinstance(hub_envelope, dict):
            proof["hub_envelope"] = hub_envelope
        proofs.append(proof)
    return proofs
