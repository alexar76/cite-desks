"""In-process Base log store, so a demo desk settles through the REAL scanner.

The point is not to fake a payment: it is to let `scan_payments` / `confirm_invoice` be
the only code that ever turns a transfer into a desk key. A fixture that shortcut
straight to `status = paid` would leave the live path untested, which is exactly how the
sibling desks ended up shipping with a checkout nobody could complete.

Never reachable in production — `fixture_allowed()` is false there and
`assert_runtime_safety` refuses to boot with PAY_MODE=fixture.
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from desk_kernel.chain import TRANSFER_TOPIC, Transfer, topic_address

TEST_TREASURY = "0x1111111111111111111111111111111111111111"


class FixtureRpc:
    def __init__(self) -> None:
        self.head = 1_000
        self._logs: list[dict[str, Any]] = []
        self._receipts: dict[str, dict[str, Any]] = {}
        self._times: dict[int, int] = {}

    def reset(self) -> None:
        self.head = 1_000
        self._logs.clear()
        self._receipts.clear()
        self._times.clear()

    def call(self, method: str, params: list[Any]) -> Any:
        if method == "eth_blockNumber":
            return hex(self.head)
        if method == "eth_getLogs":
            spec = params[0] if params else {}
            from_b = int(str(spec.get("fromBlock") or "0x0"), 16)
            to_b = int(str(spec.get("toBlock") or hex(self.head)), 16)
            addr = str(spec.get("address") or "").lower()
            topics = spec.get("topics") or []
            out: list[dict[str, Any]] = []
            for entry in self._logs:
                bn = int(entry["blockNumber"], 16)
                if bn < from_b or bn > to_b:
                    continue
                if addr and str(entry["address"]).lower() != addr:
                    continue
                if topics and topics[0] and str(entry["topics"][0]).lower() != str(topics[0]).lower():
                    continue
                if len(topics) >= 3 and topics[2] and str(entry["topics"][2]).lower() != str(topics[2]).lower():
                    continue
                out.append(entry)
            return out
        if method == "eth_getTransactionReceipt":
            return self._receipts.get(str(params[0] if params else "").lower())
        if method == "eth_getBlockByNumber":
            block = int(str(params[0] if params else "0x0"), 16)
            return {"number": hex(block), "timestamp": hex(self._times.get(block, int(time.time())))}
        raise RuntimeError(f"fixture rpc does not implement {method}")

    def inject_usdc_transfer(
        self,
        *,
        token: str,
        pay_to: str,
        amount_raw: int,
        frm: str | None = None,
        timestamp: int | None = None,
    ) -> Transfer:
        self.head += 1
        block = self.head
        self._times[block] = int(timestamp if timestamp is not None else time.time())
        tx = "0x" + secrets.token_hex(32)
        sender = (frm or ("0x" + "aa" * 20)).lower()
        entry = {
            "address": token,
            "topics": [TRANSFER_TOPIC, topic_address(sender), topic_address(pay_to)],
            "data": hex(int(amount_raw)),
            "transactionHash": tx,
            "blockNumber": hex(block),
            "logIndex": "0x0",
        }
        self._logs.append(entry)
        self._receipts[tx] = {
            "status": "0x1",
            "blockNumber": hex(block),
            "logs": [entry],
            "transactionHash": tx,
        }
        # Past the confirmation depth, or the scan would ignore its own injected transfer.
        self.head += 2
        return Transfer(
            tx_hash=tx,
            frm=sender,
            to=pay_to.lower(),
            amount_raw=int(amount_raw),
            block_number=block,
            log_index=0,
        )


_FIXTURE = FixtureRpc()


def get_fixture_rpc() -> FixtureRpc:
    return _FIXTURE


def reset_fixture_rpc() -> None:
    _FIXTURE.reset()
