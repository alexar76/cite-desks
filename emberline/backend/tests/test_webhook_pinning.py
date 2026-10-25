"""Emberline's webhook delivery connects to the address the guard vetted.

It checked the URL and then posted to it by name, so httpx resolved it again: a name that
answered public for the check and 127.0.0.1 a moment later was posted to (DNS rebinding).
"""

from __future__ import annotations

import socket

import pytest

from app import alerts


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


def test_a_webhook_is_posted_to_the_vetted_address():
    out = alerts._post_bytes("https://hooks.example.com:8443/x", b"{}", {}, channel="webhook")
    assert out["ok"] is True
    sent = _Client.sent[0]
    assert sent["url"].startswith("https://93.184.216.34:8443/")
    assert sent["headers"]["Host"] == "hooks.example.com:8443"
    assert sent["extensions"] == {"sni_hostname": "hooks.example.com"}


def test_a_slack_message_is_posted_to_the_vetted_address():
    out = alerts._post_json("https://hooks.slack.example/services/x", {"text": "hi"}, channel="slack")
    assert out["ok"] is True
    assert _Client.sent[0]["url"].startswith("https://93.184.216.34/")


def test_a_private_webhook_is_not_posted(monkeypatch):
    monkeypatch.setattr("desk_kernel.webhooks.socket.getaddrinfo",
                        lambda host, port, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port))])
    out = alerts._post_bytes("https://hooks.example.com/x", b"{}", {}, channel="webhook")
    assert out["ok"] is False and "private" in out["detail"]
    assert _Client.sent == []
