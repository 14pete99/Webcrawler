"""Tests for app.stealth.user_agent module."""

import pytest

from app.stealth.user_agent import _UA_POOL, pick_user_agent


class TestPickUserAgent:
    def test_none_returns_none(self):
        assert pick_user_agent(None) is None

    def test_random_returns_pool_entry(self):
        result = pick_user_agent("random")
        assert result is not None
        assert result in _UA_POOL

    def test_random_has_required_keys(self):
        result = pick_user_agent("random")
        assert "ua" in result
        assert "browser" in result
        assert "platform" in result

    def test_custom_ua_string_returned_as_is(self):
        custom = "Mozilla/5.0 Custom/1.0"
        result = pick_user_agent(custom)
        assert result["ua"] == custom

    def test_detects_firefox_in_custom_ua(self):
        result = pick_user_agent("Mozilla/5.0 Firefox/120.0")
        assert result["browser"] == "firefox"

    def test_detects_edge_in_custom_ua(self):
        result = pick_user_agent("Mozilla/5.0 Chrome/124 Edg/124.0.0.0")
        assert result["browser"] == "edge"

    def test_detects_chrome_in_custom_ua(self):
        result = pick_user_agent("Mozilla/5.0 Chrome/124.0.0.0 Safari/537.36")
        assert result["browser"] == "chrome"

    def test_detects_safari_in_custom_ua(self):
        result = pick_user_agent("Mozilla/5.0 Safari/604.1")
        assert result["browser"] == "safari"

    def test_unknown_browser_in_custom_ua(self):
        result = pick_user_agent("SomeBot/1.0")
        assert result["browser"] == "unknown"

    def test_mobile_platform_detected(self):
        result = pick_user_agent("Mozilla/5.0 Mobile Safari/604.1")
        assert result["platform"] == "mobile"

    def test_desktop_platform_detected(self):
        result = pick_user_agent("Mozilla/5.0 (Windows NT 10.0) Chrome/124")
        assert result["platform"] == "desktop"


class TestUAPoolIntegrity:
    def test_pool_not_empty(self):
        assert len(_UA_POOL) > 0

    def test_all_entries_have_required_keys(self):
        for entry in _UA_POOL:
            assert "ua" in entry
            assert "browser" in entry
            assert "platform" in entry

    def test_pool_has_multiple_browsers(self):
        browsers = {e["browser"] for e in _UA_POOL}
        assert len(browsers) >= 3

    def test_pool_has_desktop_and_mobile(self):
        platforms = {e["platform"] for e in _UA_POOL}
        assert "desktop" in platforms
        assert "mobile" in platforms
