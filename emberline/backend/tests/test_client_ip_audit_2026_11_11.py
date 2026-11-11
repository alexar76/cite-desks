"""Audit 2026-11-11, desks-stripe-3: the pay limiters keyed on the TCP peer, which behind the
web container is always nginx — eight invoices from anyone closed checkout for everyone."""
from types import SimpleNamespace

from app import security


def _request(peer, xff=None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


def test_the_visitor_behind_our_proxy_is_its_own_bucket():
    assert security.client_ip(_request("172.18.0.3", "203.0.113.7, 172.18.0.1")) == "203.0.113.7"
    assert security.client_ip(_request("172.18.0.3", "198.51.100.9, 172.18.0.1")) == "198.51.100.9"


def test_a_direct_caller_cannot_choose_its_bucket():
    assert security.client_ip(_request("8.8.8.8", "1.2.3.4, 5.6.7.8")) == "8.8.8.8"


def test_buckets_do_not_share_a_count():
    ip = "192.0.2.77"
    for _ in range(8):
        assert security.allow_pay_attempt(ip)
    assert not security.allow_pay_attempt(ip)
    assert security.allow_pay_attempt(ip, limit=30, bucket="confirm")
