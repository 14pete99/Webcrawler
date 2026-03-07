"""Tests for app.stealth.cloudflare module."""

import pytest

from app.stealth.cloudflare import (
    build_cf_bypass_config,
    detect_challenge_type,
    detect_cloudflare_challenge,
    turnstile_callback_js,
)


class TestDetectCloudflareChallenge:
    def test_cf_title_detected(self):
        html = "<html><title>Just a moment...</title></html>"
        assert detect_cloudflare_challenge(html) is True

    def test_cf_title_case_insensitive(self):
        html = "<html><TITLE> Just a moment... </TITLE></html>"
        assert detect_cloudflare_challenge(html) is True

    def test_cf_browser_verification_marker(self):
        html = '<div class="cf-browser-verification"></div>'
        assert detect_cloudflare_challenge(html) is True

    def test_cf_chl_marker(self):
        html = '<input name="__cf_chl_tk" value="abc">'
        assert detect_cloudflare_challenge(html) is True

    def test_challenges_cloudflare_marker(self):
        html = '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>'
        assert detect_cloudflare_challenge(html) is True

    def test_normal_html_not_detected(self):
        html = "<html><title>My Site</title><body>Hello</body></html>"
        assert detect_cloudflare_challenge(html) is False

    def test_empty_html(self):
        assert detect_cloudflare_challenge("") is False


class TestDetectChallengeType:
    def test_turnstile_type(self):
        html = '<title>Just a moment...</title><div class="cf-turnstile"></div>'
        assert detect_challenge_type(html) == "turnstile"

    def test_managed_type(self):
        html = '<title>Just a moment...</title><div id="cf-im-under-attack"></div>'
        assert detect_challenge_type(html) == "managed"

    def test_js_challenge_default(self):
        html = '<title>Just a moment...</title><script>challenge code</script>'
        assert detect_challenge_type(html) == "js_challenge"

    def test_no_challenge(self):
        html = "<html><body>Normal page</body></html>"
        assert detect_challenge_type(html) is None

    def test_turnstile_api_url(self):
        html = '<title>Just a moment...</title><script src="challenges.cloudflare.com/turnstile"></script>'
        assert detect_challenge_type(html) == "turnstile"


class TestBuildCfBypassConfig:
    def test_js_challenge_config(self):
        config = build_cf_bypass_config("js_challenge")
        assert config["page_timeout"] == 30000
        assert "wait_for" in config

    def test_turnstile_config(self):
        config = build_cf_bypass_config("turnstile")
        assert config["page_timeout"] == 60000
        assert config["delay_before_return_html"] == 8.0
        assert "turnstile-response" in config["wait_for"]

    def test_managed_config(self):
        config = build_cf_bypass_config("managed")
        assert config["page_timeout"] == 45000
        assert config["delay_before_return_html"] == 10.0

    def test_all_configs_have_base_fields(self):
        for ctype in ("js_challenge", "turnstile", "managed"):
            config = build_cf_bypass_config(ctype)
            assert "page_timeout" in config
            assert "delay_before_return_html" in config


class TestTurnstileCallbackJs:
    def test_returns_string(self):
        js = turnstile_callback_js("test-token")
        assert isinstance(js, str)

    def test_token_embedded(self):
        js = turnstile_callback_js("my-token-123")
        assert "my-token-123" in js

    def test_sets_input_value(self):
        js = turnstile_callback_js("t")
        assert "cf-turnstile-response" in js

    def test_calls_callbacks(self):
        js = turnstile_callback_js("t")
        assert "turnstileCallback" in js
        assert "__cf_chl_done" in js

    def test_special_chars_escaped(self):
        js = turnstile_callback_js("tok'en\\val")
        assert "\\'" in js
        assert "\\\\" in js
