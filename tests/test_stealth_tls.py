"""Tests for app.stealth.tls module."""

import pytest

from app.stealth.tls import TLSProfile, _TLS_PROFILES, pick_tls_profile


class TestPickTlsProfile:
    def test_chrome_ua_returns_chrome_profile(self):
        ua = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        profile = pick_tls_profile(ua)
        assert profile.browser == "chrome_124"

    def test_chrome_123_exact_match(self):
        ua = "Mozilla/5.0 Chrome/123.0.0.0 Safari/537.36"
        profile = pick_tls_profile(ua)
        assert profile.browser == "chrome_123"

    def test_firefox_ua_returns_firefox_profile(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; rv:125.0) Gecko/20100101 Firefox/125.0"
        profile = pick_tls_profile(ua)
        assert profile.browser == "firefox_125"

    def test_firefox_120_exact_match(self):
        ua = "Mozilla/5.0 Firefox/120.0"
        profile = pick_tls_profile(ua)
        assert profile.browser == "firefox_120"

    def test_edge_ua_returns_edge_profile(self):
        ua = "Mozilla/5.0 Chrome/124 Edg/124.0.0.0"
        profile = pick_tls_profile(ua)
        assert profile.browser == "edge_124"

    def test_safari_ua_returns_safari_profile(self):
        ua = "Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Version/17.4 Safari/604.1"
        profile = pick_tls_profile(ua)
        assert profile.browser == "safari_17"

    def test_unknown_version_falls_back_to_first_candidate(self):
        ua = "Mozilla/5.0 Chrome/999.0.0.0 Safari/537.36"
        profile = pick_tls_profile(ua)
        assert profile.browser == "chrome_124"  # first in chrome list

    def test_unknown_browser_falls_back_to_chrome(self):
        ua = "SomeBot/1.0"
        profile = pick_tls_profile(ua)
        assert "chrome" in profile.browser

    def test_returns_tls_profile_type(self):
        profile = pick_tls_profile("Chrome/124")
        assert isinstance(profile, TLSProfile)

    def test_profile_has_impersonate_field(self):
        profile = pick_tls_profile("Chrome/124")
        assert profile.impersonate
        assert isinstance(profile.impersonate, str)


class TestTLSProfilePool:
    def test_pool_not_empty(self):
        assert len(_TLS_PROFILES) > 0

    def test_all_have_required_fields(self):
        for p in _TLS_PROFILES:
            assert p.browser
            assert p.ja3_hash
            assert p.impersonate
