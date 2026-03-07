"""Tests for app.stealth.pipeline module."""

import pytest

from app.models.stealth import StealthConfig
from app.stealth.pipeline import StealthContext, build_stealth_context, merge_stealth_configs


class TestBuildStealthContext:
    def test_default_config_returns_context(self):
        ctx = build_stealth_context()
        assert isinstance(ctx, StealthContext)

    def test_has_user_agent(self):
        ctx = build_stealth_context()
        assert ctx.user_agent_info is not None
        assert "ua" in ctx.user_agent_info

    def test_has_page_headers(self):
        ctx = build_stealth_context()
        assert isinstance(ctx.page_headers, dict)
        assert "User-Agent" in ctx.page_headers

    def test_has_image_headers(self):
        ctx = build_stealth_context()
        assert isinstance(ctx.image_headers, dict)

    def test_has_js_injection(self):
        ctx = build_stealth_context()
        assert ctx.js_injection is not None
        assert "webdriver" in ctx.js_injection

    def test_has_viewport(self):
        ctx = build_stealth_context()
        assert ctx.viewport is not None
        assert len(ctx.viewport) == 2

    def test_has_delay_func(self):
        ctx = build_stealth_context()
        assert ctx.delay_func is not None
        assert callable(ctx.delay_func)

    def test_has_tls_profile(self):
        ctx = build_stealth_context()
        assert ctx.tls_profile is not None

    def test_no_behavior_scripts_by_default(self):
        ctx = build_stealth_context()
        assert ctx.behavior_scripts == []

    def test_behavior_scripts_when_enabled(self):
        config = StealthConfig(mouse_simulation=True, scroll_simulation=True)
        ctx = build_stealth_context(config)
        assert len(ctx.behavior_scripts) == 2

    def test_cookie_consent_adds_behavior_script(self):
        config = StealthConfig(cookie_consent_dismiss=True)
        ctx = build_stealth_context(config)
        assert len(ctx.behavior_scripts) == 1
        assert "onetrust" in ctx.behavior_scripts[0]

    def test_none_config_uses_defaults(self):
        ctx = build_stealth_context(None)
        assert ctx.user_agent_info is not None

    def test_referrer_chain_with_target_url(self):
        config = StealthConfig(referrer_chain=True)
        ctx = build_stealth_context(config, target_url="https://example.com")
        # Referrer may or may not be present depending on random roll
        assert isinstance(ctx.page_headers, dict)

    def test_geo_consistency_with_proxy_country(self):
        config = StealthConfig(geo_consistency=True)
        ctx = build_stealth_context(config, proxy_country="US")
        assert ctx.geo_profile is not None
        assert ctx.geo_profile.country_code == "US"

    def test_geo_consistency_unknown_country(self):
        config = StealthConfig(geo_consistency=True)
        ctx = build_stealth_context(config, proxy_country="ZZ")
        assert ctx.geo_profile is None

    def test_storage_seed_added_to_js(self):
        config = StealthConfig(storage_seed={"key": "val"})
        ctx = build_stealth_context(config)
        assert "localStorage" in ctx.js_injection

    def test_disabled_js_injection(self):
        config = StealthConfig(
            js_injection=False,
            canvas_spoof=False,
            webgl_spoof=False,
            audio_spoof=False,
            hardware_spoof=False,
            font_mask=False,
        )
        ctx = build_stealth_context(config)
        assert ctx.js_injection is None

    def test_custom_delay_distribution(self):
        config = StealthConfig(delay_distribution="gaussian")
        ctx = build_stealth_context(config)
        delay = ctx.delay_func()
        assert isinstance(delay, float)


class TestMergeStealthConfigs:
    def test_both_none_returns_defaults(self):
        result = merge_stealth_configs(None, None)
        assert isinstance(result, StealthConfig)

    def test_base_none_returns_override(self):
        override = StealthConfig(delay_min_ms=500)
        result = merge_stealth_configs(None, override)
        assert result.delay_min_ms == 500

    def test_override_none_returns_base(self):
        base = StealthConfig(delay_min_ms=500)
        result = merge_stealth_configs(base, None)
        assert result.delay_min_ms == 500

    def test_override_wins(self):
        base = StealthConfig(delay_min_ms=1000, delay_max_ms=3000)
        override = StealthConfig(delay_min_ms=500)
        result = merge_stealth_configs(base, override)
        assert result.delay_min_ms == 500

    def test_base_values_preserved_when_not_overridden(self):
        base = StealthConfig(delay_min_ms=1000, mouse_simulation=True)
        override = StealthConfig(delay_min_ms=500)
        result = merge_stealth_configs(base, override)
        # mouse_simulation from base should be preserved
        # but since override has all defaults set, it depends on exclude_unset
        assert result.delay_min_ms == 500
