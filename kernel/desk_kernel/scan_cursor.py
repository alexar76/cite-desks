"""Where the unattended USDC scan stopped, kept in the desk's own database.

The scan used to read a fixed window ending at the chain head (LOOKBACK_BLOCKS, about 73 min on
Base) and remember nothing. A desk down for longer than that — a host reboot, a stopped
scheduler, every RPC endpoint failing — never looked at the blocks it missed, so a buyer who paid
and closed the tab got no key unless they came back and pasted the hash (audit 2026-11-11,
desks-stripe-8). The cursor makes the next scan start where the last finished one ended, back to
at most the invoice claim window (TTL + late grace, see ``catchup_blocks``): an older transfer
could not settle anything anyway.

One small table, created on first use, so neither the kernel nor a desk built on it needs a
schema migration for it. Plain SQL that SQLite and PostgreSQL both accept.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .chain import LOOKBACK_BLOCKS

#: Fallback catch-up when the caller passes no claim window: about 24 h of Base blocks (2 s).
MAX_CATCHUP_BLOCKS = 43_200
SECONDS_PER_BLOCK = 2


def catchup_blocks(*, invoice_ttl_minutes: int, late_grace_hours: int) -> int:
    """Blocks back to the oldest transfer an invoice could still be claimed with.

    An invoice stays claimable until expires_at + late grace, i.e. its TTL plus the grace after
    it was created; a fixed 24 h fell short of that by up to the TTL (review of 2026-11-11).
    One lookback window of margin on top.
    """
    seconds = max(0, int(invoice_ttl_minutes)) * 60 + max(0, int(late_grace_hours)) * 3600
    return seconds // SECONDS_PER_BLOCK + LOOKBACK_BLOCKS

_DDL = "CREATE TABLE IF NOT EXISTS pay_scan_cursor (scan_key VARCHAR(64) PRIMARY KEY, block BIGINT NOT NULL)"


def _ensure(db: Session) -> None:
    db.execute(text(_DDL))


def load_cursor(db: Session, key: str = "usdc_base") -> int | None:
    """The last block a finished scan covered, or None before the first one."""
    _ensure(db)
    row = db.execute(text("SELECT block FROM pay_scan_cursor WHERE scan_key = :k"), {"k": key}).first()
    return int(row[0]) if row else None


def scan_start(db: Session, settled_head: int, key: str = "usdc_base", *,
               max_catchup_blocks: int = MAX_CATCHUP_BLOCKS) -> int:
    """First block of this scan: the usual window, or earlier when the last scan is behind it."""
    floor = settled_head - LOOKBACK_BLOCKS
    cursor = load_cursor(db, key)
    start = floor if cursor is None else min(floor, cursor + 1)
    return max(0, start, settled_head - max(int(max_catchup_blocks), LOOKBACK_BLOCKS))


def save_cursor(db: Session, block: int, key: str = "usdc_base") -> None:
    """Record that every block up to ``block`` was scanned. Call only after a full walk."""
    _ensure(db)
    updated = db.execute(text("UPDATE pay_scan_cursor SET block = :b WHERE scan_key = :k"),
                         {"b": int(block), "k": key})
    if not updated.rowcount:
        db.execute(text("INSERT INTO pay_scan_cursor (scan_key, block) VALUES (:k, :b)"),
                   {"k": key, "b": int(block)})
    db.commit()
