"""The in-process Base log store now lives in the kernel; this is the import site.

Emberline and its sibling desks settle demo payments through the same fake chain and the
same real scanner. Keeping a second copy here meant a fixture that could drift from the
scanner it is supposed to exercise.
"""

from __future__ import annotations

from desk_kernel.service.payfixture import (
    TEST_TREASURY,
    FixtureRpc,
    get_fixture_rpc,
    reset_fixture_rpc,
)

__all__ = ["TEST_TREASURY", "FixtureRpc", "get_fixture_rpc", "reset_fixture_rpc"]
