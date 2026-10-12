"""Shared kernel for independent evidence desks.

Desks (Emberline, Tideline, Solrecord, Seamark, Plinth) own brand and claim class.
This package owns Hub custody, USDC salt invoices, HMAC webhooks, cite packs,
bbox/point watches, receipt checks, and the fail-closed LIVE vs SIM rule.
"""

from .claim import ClaimClass, HostRegion, WatchKind
from .geo import BBoxError, interval_minutes, validate_bbox, validate_point
from .hmac import sign_webhook, verify_webhook
from .hub import HubClient, HubError
from .receipt import verify_receipt

__version__ = "0.1.0"

__all__ = [
    "BBoxError",
    "ClaimClass",
    "HubClient",
    "HubError",
    "HostRegion",
    "WatchKind",
    "interval_minutes",
    "sign_webhook",
    "validate_bbox",
    "validate_point",
    "verify_receipt",
    "verify_webhook",
]
