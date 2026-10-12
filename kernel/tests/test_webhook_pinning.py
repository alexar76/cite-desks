"""Webhook delivery connects to the address the guard vetted, and is off on demo desks."""

from __future__ import annotations

import os
import socket

import pytest

from desk_kernel.service import alerts
from desk_kernel.service.config import get_settings


class _Client:
    sent: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, content=None, headers=None, extensions=None):
        _Client.sent.append({"url": url, "headers": headers, "extensions": extensions})
        import httpx

        return httpx.Response(200, request=httpx.Request("POST", url))


@pytest.fixture(autouse=True)
def _wired(monkeypatch):
    _Client.sent = []
    answers = iter(["93.184.216.34", "127.0.0.1"])   # check sees public; a second lookup would see loopback

    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(answers), port))]

    monkeypatch.setattr("desk_kernel.webhooks.socket.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(alerts.httpx, "Client", _Client)
    os.environ.pop("DESK_MODE", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_delivery_connects_to_the_vetted_address_not_a_second_lookup():
    out = alerts._post_bytes("https://hooks.example.com/x", b"{}", {}, channel="webhook")
    assert out["ok"] is True
    sent = _Client.sent[0]
    assert sent["url"].startswith("https://93.184.216.34/")
    assert sent["headers"]["Host"] == "hooks.example.com"
    assert sent["extensions"] == {"sni_hostname": "hooks.example.com"}


def test_the_demo_desk_does_not_deliver_webhooks(monkeypatch):
    monkeypatch.setenv("DESK_MODE", "demo")
    get_settings.cache_clear()
    out = alerts._post_bytes("https://hooks.example.com/x", b"{}", {}, channel="webhook")
    assert out["ok"] is False and "demo" in out["detail"]
    assert _Client.sent == []
