"""Base / USDC settlement primitives shared by every desk.

Nothing here reads Settings or a ClaimClass: the caller passes a `ChainConfig`, so the
same code serves a live desk, a test, and the in-process fixture RPC. Emberline grew this
logic first (`emberline/backend/app/basepay.py`); the constants and the reasons for them
are carried over verbatim because they were each paid for by a real failure.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

log = logging.getLogger(__name__)

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
TX_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
USDC_DECIMALS = 6
#: How far back a scan looks. Base mints every ~2s, so this is a bit over an hour — more
#: than the default invoice TTL plus a slow wallet, and short enough to stay cheap.
LOOKBACK_BLOCKS = 2_200
# ...but NEVER in one request. Measured against all eleven live public Base endpoints on
# 2026-09-11: six serve a 1000-block eth_getLogs, publicnode serves 10 000, 1rpc caps at
# 50 ("eth_getLogs is limited to 0 - 50 blocks range"), mainnet.base.org answers 413 and
# others refuse outright. A single 2200-block ask therefore only succeeded when failover
# happened to land on publicnode; every other endpoint refused and the scan raised.
# Chunk instead, and narrow when an endpoint says the window is too wide.
LOG_WINDOW_BLOCKS = 1_000
LOG_WINDOW_MIN = 50
#: Provider wording for "your window is too wide". They are not transport errors and not
#: malformed requests — they mean ask for less, which is the one response a scanner can
#: act on. (drpc/tenderly return -32602, which reads like a bad request; blockpi and
#: publicnode say "exceeds max results"; 1rpc names the limit outright.)
_RANGE_REFUSALS = (
    "limited to",
    "block range too large",
    "exceeds max results",
    "range too large",
    "too many blocks",
    "query returned more than",
    "response size exceeded",
    "413",
    "payload too large",
)
RPC_TIMEOUT_S = 10.0
DEFAULT_USER_AGENT = "cite-desk/0.1"
DEFAULT_BASE_RPC_URLS = (
    "https://mainnet.base.org",
    "https://base-rpc.publicnode.com",
    "https://1rpc.io/base",
    "https://base.drpc.org",
    "https://base.gateway.tenderly.co",
)
#: Semicolons included on purpose: operators write `a;b` as often as `a,b`, and without it
#: the pair survives as one "URL" that starts with https:// and then fails every call.
_RPC_SPLIT = re.compile(r"[,;\s]+")


class RpcError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChainConfig:
    """Everything the settlement code needs to know about one desk's treasury."""

    token: str
    pay_to: str
    chain_id: int
    confirmations: int
    rpc_urls: tuple[str, ...]
    user_agent: str = DEFAULT_USER_AGENT


class Rpc(Protocol):
    def call(self, method: str, params: list[Any]) -> Any: ...


class HttpRpc:
    def __init__(self, url: str, *, user_agent: str = DEFAULT_USER_AGENT, timeout: float = RPC_TIMEOUT_S) -> None:
        self.url = url
        self.user_agent = user_agent
        self.timeout = timeout

    def call(self, method: str, params: list[Any]) -> Any:
        try:
            response = httpx.post(
                self.url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RpcError(f"{self.url}: {exc}") from exc
        if payload.get("error"):
            raise RpcError(f"{self.url}: {payload['error']}")
        return payload.get("result")


class FailoverRpc:
    """Sticky round-robin over public endpoints. One flaky host must not close checkout."""

    def __init__(
        self,
        urls: list[str] | tuple[str, ...],
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        clients: list[Rpc] | None = None,
    ) -> None:
        urls = list(urls)
        if not urls:
            raise RpcError("PAY_BASE_RPC_URL is not set and no default endpoint survived")
        self.urls = urls
        self.endpoints = clients or [HttpRpc(url, user_agent=user_agent) for url in urls]
        self._index = 0
        self._lock = threading.Lock()

    def call(self, method: str, params: list[Any]) -> Any:
        with self._lock:
            start = self._index
            n = len(self.endpoints)
        last: Exception | None = None
        for step in range(n):
            i = (start + step) % n
            try:
                result = self.endpoints[i].call(method, params)
            except RpcError as exc:
                last = exc
                log.warning("base rpc %s failed: %s", self.urls[i], exc)
                continue
            with self._lock:
                if self._index != i:
                    log.warning("base rpc failover %s -> %s", self.urls[self._index], self.urls[i])
                self._index = i
            return result
        raise RpcError(f"all rpc endpoints failed: {last}") from last


def parse_rpc_urls(raw: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for part in _RPC_SPLIT.split((raw or "").strip()):
        url = part.strip().rstrip("/")
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def rpc_url_list(raw: str) -> list[str]:
    """Operator-supplied endpoints first, then the built-in public Base backups."""
    urls = parse_rpc_urls(raw)
    seen = set(urls)
    for url in DEFAULT_BASE_RPC_URLS:
        if url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def normalize_address(value: str) -> str:
    addr = (value or "").strip()
    if not ADDRESS_RE.match(addr):
        raise ValueError("invalid address")
    return addr.lower()


def is_address(value: str) -> bool:
    return bool(ADDRESS_RE.match((value or "").strip()))


def topic_address(addr: str) -> str:
    return "0x" + normalize_address(addr)[2:].zfill(64)


def decode_address(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def decode_uint(data: str) -> int:
    return int(data, 16) if data else 0


def format_usdc(amount_raw: int) -> str:
    whole, frac = divmod(int(amount_raw), 10**USDC_DECIMALS)
    return f"{whole}.{frac:06d}"


def explorer_base(chain_id: int) -> str:
    if chain_id == 84532:
        return "https://sepolia.basescan.org"
    return "https://basescan.org"


def eip681(*, token: str, chain_id: int, to: str, amount_raw: int) -> str:
    return f"ethereum:{token}@{chain_id}/transfer?address={to}&uint256={amount_raw}"


@dataclass(frozen=True)
class Transfer:
    tx_hash: str
    frm: str
    to: str
    amount_raw: int
    block_number: int
    log_index: int


def parse_transfer_logs(logs: list[dict[str, Any]], *, token: str, pay_to: str) -> list[Transfer]:
    token_n = normalize_address(token)
    pay_n = normalize_address(pay_to)
    out: list[Transfer] = []
    for entry in logs:
        if normalize_address(str(entry.get("address") or "")) != token_n:
            continue
        topics = [str(t) for t in (entry.get("topics") or [])]
        if len(topics) < 3 or topics[0].lower() != TRANSFER_TOPIC:
            continue
        dest = decode_address(topics[2])
        if dest != pay_n:
            continue
        out.append(
            Transfer(
                tx_hash=str(entry.get("transactionHash") or "").lower(),
                frm=decode_address(topics[1]),
                to=dest,
                amount_raw=decode_uint(str(entry.get("data") or "0x0")),
                block_number=int(entry.get("blockNumber") or "0x0", 16),
                log_index=int(entry.get("logIndex") or "0x0", 16),
            )
        )
    return out


def _is_range_refusal(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _RANGE_REFUSALS)


def _fetch_window(rpc: Rpc, cfg: ChainConfig, lo: int, hi: int) -> list[Any]:
    logs = rpc.call(
        "eth_getLogs",
        [
            {
                "address": cfg.token,
                "fromBlock": hex(lo),
                "toBlock": hex(hi),
                "topics": [TRANSFER_TOPIC, None, topic_address(cfg.pay_to)],
            }
        ],
    )
    if not isinstance(logs, list):
        raise RpcError("eth_getLogs returned non-list")
    return logs


def fetch_transfers(rpc: Rpc, cfg: ChainConfig, *, from_block: int, to_block: int) -> list[Transfer]:
    """USDC transfers into the treasury over [from_block, to_block], in chunks.

    When an endpoint answers "that window is too wide" the step halves and the same span
    is retried, down to LOG_WINDOW_MIN — so the scan adapts to whichever endpoint failover
    landed on instead of failing the whole poll. Any other error still propagates: a
    scanner that swallows everything is indistinguishable from one watching an address
    nobody has paid.
    """
    raw: list[Any] = []
    lo = int(from_block)
    end = int(to_block)
    step = LOG_WINDOW_BLOCKS
    while lo <= end:
        hi = min(lo + step - 1, end)
        try:
            raw.extend(_fetch_window(rpc, cfg, lo, hi))
        except RpcError as exc:
            if _is_range_refusal(exc) and step > LOG_WINDOW_MIN:
                step = max(LOG_WINDOW_MIN, step // 2)
                log.warning(
                    "chain: endpoint refused a %d-block log window, narrowing to %d",
                    hi - lo + 1, step,
                )
                continue          # same `lo`, smaller window
            raise
        lo = hi + 1
    return parse_transfer_logs(raw, token=cfg.token, pay_to=cfg.pay_to)


def current_block(rpc: Rpc) -> int:
    return int(rpc.call("eth_blockNumber", []), 16)


def fetch_receipt(rpc: Rpc, tx_hash: str) -> dict[str, Any]:
    if not TX_RE.match(tx_hash):
        raise ValueError("invalid tx hash")
    receipt = rpc.call("eth_getTransactionReceipt", [tx_hash])
    if not isinstance(receipt, dict):
        raise RpcError("receipt not found")
    return receipt


def transfers_from_receipt(cfg: ChainConfig, receipt: dict[str, Any]) -> list[Transfer]:
    return parse_transfer_logs(list(receipt.get("logs") or []), token=cfg.token, pay_to=cfg.pay_to)


def block_time(rpc: Rpc, block_number: int) -> datetime:
    block = rpc.call("eth_getBlockByNumber", [hex(int(block_number)), False])
    stamp = block.get("timestamp") if isinstance(block, dict) else None
    if not stamp:
        raise RpcError("block timestamp is unavailable")
    return datetime.fromtimestamp(int(str(stamp), 16), timezone.utc)
