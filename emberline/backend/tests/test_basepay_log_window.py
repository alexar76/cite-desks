"""The payment scan must survive an endpoint that refuses wide eth_getLogs windows.

Measured 2026-09-11 against all eleven live public Base endpoints: six serve 1000 blocks,
publicnode 10 000, 1rpc caps at 50, mainnet.base.org answers 413. LOOKBACK_BLOCKS is 2200,
so a single request only worked when failover happened to land on publicnode — and when it
did not, FailoverRpc exhausted the list, raised, and the scheduler swallowed it without a
log line. Customers' USDC then settled on nobody's books.
"""
from __future__ import annotations

import pytest

from app import basepay


class NarrowWindowRpc:
    """An endpoint like 1rpc: serves 50 blocks and refuses anything wider."""

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit
        self.windows: list[tuple[int, int]] = []
        self.refusals = 0

    def call(self, method, params):
        if method == "eth_blockNumber":
            return hex(1_000_000)
        if method != "eth_getLogs":
            raise AssertionError(method)
        lo = int(params[0]["fromBlock"], 16)
        hi = int(params[0]["toBlock"], 16)
        if hi - lo + 1 > self.limit:
            self.refusals += 1
            raise basepay.RpcError(
                "https://1rpc.io/base: eth_getLogs is limited to 0 - %d blocks range" % self.limit
            )
        self.windows.append((lo, hi))
        return []


def test_a_narrow_endpoint_still_gets_the_whole_range_scanned():
    rpc = NarrowWindowRpc(limit=50)
    out = basepay.fetch_transfers(from_block=1_000, to_block=1_499, rpc=rpc)
    assert out == []
    assert rpc.refusals > 0, "the fixture never exercised the refusal path"
    # Every block in [1000, 1499] is covered exactly once, with no gaps.
    covered: set[int] = set()
    for lo, hi in rpc.windows:
        assert hi - lo + 1 <= 50
        for b in range(lo, hi + 1):
            assert b not in covered, f"block {b} scanned twice"
            covered.add(b)
    assert covered == set(range(1_000, 1_500)), "the scan left a hole in the range"


def test_a_wide_endpoint_is_not_punished_with_tiny_windows():
    """An endpoint that serves the default window must be asked for the default window."""
    rpc = NarrowWindowRpc(limit=10_000)
    basepay.fetch_transfers(from_block=0, to_block=basepay.LOG_WINDOW_BLOCKS - 1, rpc=rpc)
    assert rpc.refusals == 0
    assert rpc.windows == [(0, basepay.LOG_WINDOW_BLOCKS - 1)]


def test_a_non_range_error_is_not_silently_absorbed():
    """Only 'ask for less' is recoverable. Anything else must reach the caller."""

    class Broken:
        def call(self, method, params):
            if method == "eth_blockNumber":
                return hex(10)
            raise basepay.RpcError("https://x: 401 Client Error: Unauthorized")

    with pytest.raises(basepay.RpcError):
        basepay.fetch_transfers(from_block=0, to_block=10, rpc=Broken())
