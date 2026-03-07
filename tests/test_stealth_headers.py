"""Tests for app.stealth.headers module."""

import pytest

from app.stealth.headers import (
    _guess_platform,
    add_conditional_headers,
    build_headers,
    build_image_headers,
    generate_headers,
)


def _chrome_ua():
    return {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "browser": "chrome",
        "platform": "desktop",
    }


def _firefox_ua():
    return {
        "ua": "Mozilla/5.0 (Windows NT 10.0; rv:125.0) Gecko/20100101 Firefox/125.0",
        "browser": "firefox",
        "platform": "desktop",
    }


class TestBuildHeaders:
    def test_none_strategy_returns_empty(self):
        assert build_headers(_chrome_ua(), strategy=None) == {}

    def test_minimal_strategy(self):
        headers = build_headers(_chrome_ua(), strategy="minimal")
        assert "User-Agent" in headers
        assert headers["Accept"] == "*/*"
        assert "Sec-Ch-Ua" not in headers

    def test_realistic_chrome_has_sec_headers(self):
        headers = build_headers(_chrome_ua(), strategy="realistic")
        assert "Sec-Ch-Ua" in headers
        assert "Sec-Ch-Ua-Mobile" in headers
        assert "Sec-Ch-Ua-Platform" in headers
        assert "Sec-Fetch-Dest" in headers

    def test_realistic_firefox_no_sec_headers(self):
        headers = build_headers(_firefox_ua(), strategy="realistic")
        assert "Sec-Ch-Ua" not in headers
        assert "Accept-Language" in headers

    def test_ua_string_included(self):
        ua = _chrome_ua()
        headers = build_headers(ua)
        assert headers["User-Agent"] == ua["ua"]

    def test_none_ua_no_user_agent_header(self):
        headers = build_headers(None, strategy="realistic")
        assert "User-Agent" not in headers

    def test_referrer_included(self):
        headers = build_headers(_chrome_ua(), referrer="https://google.com")
        assert headers["Referer"] == "https://google.com"

    def test_mobile_chrome_has_mobile_sec_header(self):
        ua = _chrome_ua()
        ua["platform"] = "mobile"
        headers = build_headers(ua)
        assert headers["Sec-Ch-Ua-Mobile"] == "?1"


class TestBuildImageHeaders:
    def test_none_strategy_returns_empty(self):
        assert build_image_headers(_chrome_ua(), strategy=None) == {}

    def test_minimal_has_image_accept(self):
        headers = build_image_headers(_chrome_ua(), strategy="minimal")
        assert "image/*" in headers["Accept"]

    def test_realistic_has_avif_accept(self):
        headers = build_image_headers(_chrome_ua())
        assert "image/avif" in headers["Accept"]

    def test_chrome_has_sec_fetch_image(self):
        headers = build_image_headers(_chrome_ua())
        assert headers["Sec-Fetch-Dest"] == "image"
        assert headers["Sec-Fetch-Mode"] == "no-cors"

    def test_referer_included(self):
        headers = build_image_headers(_chrome_ua(), referer="https://example.com")
        assert headers["Referer"] == "https://example.com"

    def test_firefox_no_sec_fetch(self):
        headers = build_image_headers(_firefox_ua())
        assert "Sec-Fetch-Dest" not in headers


class TestGenerateHeaders:
    def test_basic_ua_string(self):
        headers = generate_headers("Mozilla/5.0 Chrome/124")
        assert "User-Agent" in headers

    def test_with_referrer(self):
        headers = generate_headers("Mozilla/5.0 Chrome/124", referrer="https://ref.com")
        assert headers["Referer"] == "https://ref.com"

    def test_with_cache_state(self):
        headers = generate_headers(
            "Mozilla/5.0 Chrome/124",
            cache_state={"etag": '"abc"', "last_modified": "Wed, 01 Jan 2025"},
        )
        assert headers["If-None-Match"] == '"abc"'
        assert headers["If-Modified-Since"] == "Wed, 01 Jan 2025"

    def test_detects_firefox_browser(self):
        headers = generate_headers("Mozilla/5.0 Firefox/125.0")
        assert "Sec-Ch-Ua" not in headers

    def test_detects_edge_browser(self):
        headers = generate_headers("Mozilla/5.0 Chrome/124 Edg/124")
        assert "Sec-Ch-Ua" in headers


class TestAddConditionalHeaders:
    def test_adds_etag(self):
        h = add_conditional_headers({}, etag='"123"')
        assert h["If-None-Match"] == '"123"'

    def test_adds_last_modified(self):
        h = add_conditional_headers({}, last_modified="Mon, 01 Jan 2025")
        assert h["If-Modified-Since"] == "Mon, 01 Jan 2025"

    def test_noop_when_none(self):
        h = add_conditional_headers({"Existing": "value"})
        assert h == {"Existing": "value"}


class TestGuessPlatform:
    def test_windows(self):
        assert _guess_platform({"ua": "Windows NT 10.0", "browser": "chrome", "platform": "desktop"}) == '"Windows"'

    def test_macos(self):
        assert _guess_platform({"ua": "Macintosh; Intel Mac OS X", "browser": "chrome", "platform": "desktop"}) == '"macOS"'

    def test_linux(self):
        assert _guess_platform({"ua": "X11; Linux x86_64", "browser": "chrome", "platform": "desktop"}) == '"Linux"'

    def test_android(self):
        assert _guess_platform({"ua": "Linux; Android 14", "browser": "chrome", "platform": "mobile"}) == '"Android"'

    def test_ios(self):
        assert _guess_platform({"ua": "iPhone; CPU iPhone OS", "browser": "safari", "platform": "mobile"}) == '"iOS"'

    def test_none_ua_defaults_windows(self):
        assert _guess_platform(None) == '"Windows"'
