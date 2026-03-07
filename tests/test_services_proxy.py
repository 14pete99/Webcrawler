"""Tests for app.services.proxy module."""

import pytest

from app.services.proxy import ProxyEntry, ProxyPool, _parse_proxy_line


class TestParseProxyLine:
    def test_url_only(self):
        entry = _parse_proxy_line("http://proxy:8080")
        assert entry.url == "http://proxy:8080"
        assert entry.proxy_type == "datacenter"
        assert entry.country is None
        assert entry.city is None

    def test_url_and_type(self):
        entry = _parse_proxy_line("http://proxy:8080|residential")
        assert entry.url == "http://proxy:8080"
        assert entry.proxy_type == "residential"

    def test_url_type_country(self):
        entry = _parse_proxy_line("http://proxy:8080|residential|US")
        assert entry.country == "US"

    def test_full_format(self):
        entry = _parse_proxy_line("http://proxy:8080|mobile|DE|Berlin")
        assert entry.url == "http://proxy:8080"
        assert entry.proxy_type == "mobile"
        assert entry.country == "DE"
        assert entry.city == "Berlin"

    def test_strips_whitespace(self):
        entry = _parse_proxy_line("  http://proxy:8080 | residential | US | NYC ")
        assert entry.url == "http://proxy:8080"
        assert entry.proxy_type == "residential"
        assert entry.country == "US"
        assert entry.city == "NYC"


class TestProxyPool:
    def test_empty_pool(self):
        pool = ProxyPool()
        assert pool.count == 0
        assert pool.is_empty
        assert pool.next() is None

    def test_single_proxy(self):
        pool = ProxyPool([ProxyEntry(url="http://p1:8080")])
        assert pool.count == 1
        assert not pool.is_empty

    def test_next_cycles(self):
        pool = ProxyPool([
            ProxyEntry(url="http://p1:8080"),
            ProxyEntry(url="http://p2:8080"),
        ])
        assert pool.next().url == "http://p1:8080"
        assert pool.next().url == "http://p2:8080"
        assert pool.next().url == "http://p1:8080"

    def test_next_by_type(self):
        pool = ProxyPool([
            ProxyEntry(url="http://p1:8080", proxy_type="datacenter"),
            ProxyEntry(url="http://p2:8080", proxy_type="residential"),
        ])
        result = pool.next_by_type("residential")
        assert result.url == "http://p2:8080"

    def test_next_by_type_not_found(self):
        pool = ProxyPool([ProxyEntry(url="http://p1:8080")])
        assert pool.next_by_type("mobile") is None

    def test_next_by_country(self):
        pool = ProxyPool([
            ProxyEntry(url="http://p1:8080", country="US"),
            ProxyEntry(url="http://p2:8080", country="DE"),
        ])
        result = pool.next_by_country("DE")
        assert result.url == "http://p2:8080"

    def test_next_by_country_case_insensitive(self):
        pool = ProxyPool([ProxyEntry(url="http://p1:8080", country="US")])
        result = pool.next_by_country("us")
        assert result is not None

    def test_next_by_country_not_found(self):
        pool = ProxyPool([ProxyEntry(url="http://p1:8080", country="US")])
        assert pool.next_by_country("ZZ") is None


class TestProxyPoolFromArgs:
    def test_single_proxy_arg(self):
        pool = ProxyPool.from_args(proxy="http://p1:8080")
        assert pool.count == 1
        assert pool.next().url == "http://p1:8080"

    def test_proxy_file(self, tmp_path):
        pfile = tmp_path / "proxies.txt"
        pfile.write_text("http://p1:8080\n# comment\nhttp://p2:8080|residential|US\n\n")
        pool = ProxyPool.from_args(proxy_file=str(pfile))
        assert pool.count == 2

    def test_both_proxy_and_file(self, tmp_path):
        pfile = tmp_path / "proxies.txt"
        pfile.write_text("http://p2:8080\n")
        pool = ProxyPool.from_args(proxy="http://p1:8080", proxy_file=str(pfile))
        assert pool.count == 2
        assert pool.next().url == "http://p1:8080"
        assert pool.next().url == "http://p2:8080"

    def test_no_args(self):
        pool = ProxyPool.from_args()
        assert pool.is_empty

    def test_file_with_metadata(self, tmp_path):
        pfile = tmp_path / "proxies.txt"
        pfile.write_text("http://p1:8080|residential|US|NYC\n")
        pool = ProxyPool.from_args(proxy_file=str(pfile))
        entry = pool.next()
        assert entry.proxy_type == "residential"
        assert entry.country == "US"
        assert entry.city == "NYC"
