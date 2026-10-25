"""Serialize amount reservation until the invoice has been committed.

An exact USDC amount is the payment reference. Two workers must not read the
same available amount and both quote it, even when they use separate processes.
"""
from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

_allocation_lock = RLock()
_POSTGRES_LOCK = 0x43495445504159
PAYMENT_SALT_MAX = 20_000
PAYMENT_SALT_BANDS = 10
_LEGACY_SALT_END = 10_000
_DESK_BANDS = {"solrecord": 0, "smokeproof": 1, "seamark": 2,
               "plinth": 3, "tideline": 4, "emberline": 5}


def payment_salt_band(desk_id: str) -> tuple[int, int]:
    """Explicit namespaces: hashing six IDs into ten buckets causes collisions."""
    if desk_id not in _DESK_BANDS:
        raise ValueError("desk has no reserved payment amount namespace")
    # The first 9,999 raw units were used by overlapping legacy namespaces.
    # New quotes must not collide with still-payable legacy invoices on any desk.
    width = (PAYMENT_SALT_MAX - _LEGACY_SALT_END) // PAYMENT_SALT_BANDS
    band = _DESK_BANDS[desk_id]
    return _LEGACY_SALT_END + band * width + 1, _LEGACY_SALT_END + (band + 1) * width


def quote_needs_reconciliation(amount_raw: int, desk_id: str) -> bool:
    """Old overlapping quotes cannot safely grant access from an amount alone."""
    lo, hi = payment_salt_band(desk_id)
    return not lo <= int(amount_raw) % 1_000_000 < hi


@contextmanager
def reserve_invoice_amount(db: Session) -> Iterator[None]:
    # Also protect SQLite's shared in-memory test connection within one process.
    with _allocation_lock:
        try:
            dialect = db.get_bind().dialect.name
            if dialect == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _POSTGRES_LOCK})
            elif dialect == "sqlite":
                connection = db.connection()
                if not connection.connection.driver_connection.in_transaction:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                raise RuntimeError("invoice amount reservation needs PostgreSQL or SQLite")
            yield
        except Exception:
            db.rollback()
            raise
