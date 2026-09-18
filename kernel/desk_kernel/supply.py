"""What a desk says when it could not buy the evidence it sells.

Settings-free on purpose, like `chain`: Emberline's engine and the kernel's engine both
import it, so a customer of any desk in the family gets the same honest sentence and an
operator gets the same machine-readable cause.
"""

from __future__ import annotations

from datetime import datetime, timezone

#: Cause markers matched against the upstream error text, in order. The raw text stays in
#: `run.error` for the operator: it carries the upstream's own prices, free allowance and
#: "open a payment channel" instructions — the desk's supplier terms, none of a paying
#: customer's business. Worse, a customer reading them would reasonably conclude the
#: failure was theirs to fix.
_NOT_YOUR_FAULT = " Nothing was charged to your plan"
SUPPLY_FAILURES: tuple[tuple[str, str, str], ...] = (
    ("hub 402", "supply_unpaid",
     "This desk cannot buy evidence right now." + _NOT_YOUR_FAULT + "; the operator has been alerted."),
    ("payment_required", "supply_unpaid",
     "This desk cannot buy evidence right now." + _NOT_YOUR_FAULT + "; the operator has been alerted."),
    ("hub 429", "supply_throttled",
     "The evidence source is rate-limiting this desk." + _NOT_YOUR_FAULT + "; try again shortly."),
    ("hub unreachable", "supply_unreachable",
     "The evidence source did not answer." + _NOT_YOUR_FAULT + "; try again shortly."),
)
PUBLIC_FAILURE_FALLBACK = "This run could not be completed." + _NOT_YOUR_FAULT + "."

#: Last time this process could not buy evidence. Plans already sold are worth nothing while
#: this is fresh, so it belongs next to the checkout state an operator already reads.
_supply_failure: dict[str, object] = {"at": None, "kind": "", "detail": ""}


def failure_summary(error: str | None) -> dict[str, str]:
    """Customer-safe rendering of a failed run, plus a machine-readable cause."""
    if not error:
        return {"kind": "", "message": ""}
    haystack = error.lower()
    for marker, kind, message in SUPPLY_FAILURES:
        if marker in haystack:
            return {"kind": kind, "message": message}
    return {"kind": "run_failed", "message": PUBLIC_FAILURE_FALLBACK}


def note_supply_failure(at: datetime, kind: str, detail: str) -> None:
    # Callers pass a timestamp straight off the run row, and a row read back from SQLite
    # comes without a timezone. Storing it as-is made /api/public/health raise on the next
    # request — the one endpoint that has to work when everything else is broken.
    stamp = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    _supply_failure.update(at=stamp, kind=kind, detail=(detail or "")[:400])


def last_supply_failure() -> dict[str, object]:
    at = _supply_failure["at"]
    return {
        "at": at.isoformat() if at else None,
        "age_seconds": round((datetime.now(timezone.utc) - at).total_seconds(), 1) if at else None,
        "kind": _supply_failure["kind"] or None,
        "detail": _supply_failure["detail"] or None,
    }


#: Headers the upstream puts on a charged call. Read here rather than in each desk's hub
#: client because there are two of those clients (kernel and Emberline) and a balance an
#: operator can only see in one of them is a balance nobody watches.
BALANCE_HEADER = "x-atlas-credit-balance-usd"
CHARGED_HEADER = "x-atlas-credit-charged-usd"
LOW_BALANCE_HEADER = "x-atlas-credit-low"

#: What the desk's prepaid account looked like on its last purchase. `supply_unpaid` above
#: is the failure this exists to pre-empt: by the time it fires, a customer's run has
#: already failed, so an operator needs the balance while it is still falling.
_supply_credit: dict[str, object] = {"at": None, "seller": "", "balance_usd": None,
                                     "charged_usd": None, "low": False}


def note_supply_credit(headers: object, seller: str = "") -> None:
    """Record the balance reported by a successful purchase. Silent if the rail is off.

    `seller` is named in the result because a desk buys from more than one: reporting a
    balance without saying whose would let an operator read a healthy ATLAS account as
    proof that the sensor-relay account is funded too.

    Tolerant of anything mapping-like and of junk values: a header that cannot be parsed
    must not turn a delivered purchase into a failed run.
    """
    getter = getattr(headers, "get", None)
    if getter is None:
        return
    balance = _as_float(getter(BALANCE_HEADER))
    if balance is None:
        return
    _supply_credit.update(
        at=datetime.now(timezone.utc),
        seller=seller,
        balance_usd=balance,
        charged_usd=_as_float(getter(CHARGED_HEADER)),
        low=str(getter(LOW_BALANCE_HEADER) or "").strip() in {"1", "true", "yes"},
    )


def _as_float(value: object) -> float | None:
    try:
        return round(float(value), 6)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def last_supply_credit() -> dict[str, object]:
    at = _supply_credit["at"]
    return {
        "at": at.isoformat() if at else None,
        "age_seconds": round((datetime.now(timezone.utc) - at).total_seconds(), 1) if at else None,
        "seller": _supply_credit["seller"] or None,
        "balance_usd": _supply_credit["balance_usd"],
        "charged_usd": _supply_credit["charged_usd"],
        "low": bool(_supply_credit["low"]),
    }
