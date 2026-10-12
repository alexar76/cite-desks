from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google.com",
}


class UnsafeWebhook(ValueError):
    pass


def _deliverable(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _deliverable(ip.ipv4_mapped)
        # NAT64 and 6to4 report is_global=True while carrying an IPv4 address inside.
        if ip in ipaddress.ip_network("64:ff9b::/96") or ip in ipaddress.ip_network("2002::/16"):
            return False
    return ip.is_global and not ip.is_multicast


def resolve_safe_webhook(url: str) -> tuple[str, str]:
    """(url, the vetted address to connect to), from ONE resolution. Delivery must connect
    to this address: resolving again at connect time let a short-TTL name pass the check
    and then point somewhere private (DNS rebinding)."""
    return _vet(url)


def assert_safe_webhook_url(url: str) -> str:
    return _vet(url)[0] if (url or "").strip() else ""


def _vet(url: str) -> tuple[str, str]:
    raw = (url or "").strip()
    if not raw:
        return "", ""
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise UnsafeWebhook("webhook URL must be https")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".localhost"):
        raise UnsafeWebhook("webhook host is not allowed")
    if host.endswith(".internal") or host.endswith(".local"):
        raise UnsafeWebhook("webhook host is not allowed")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeWebhook("webhook host does not resolve") from exc
    if not infos:
        raise UnsafeWebhook("webhook host does not resolve")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not _deliverable(ip):
            raise UnsafeWebhook("webhook resolves to a private or reserved address")
    return raw, str(infos[0][4][0])
