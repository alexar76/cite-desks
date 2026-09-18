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


def assert_safe_webhook_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
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
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeWebhook("webhook resolves to a private or reserved address")
    return raw
