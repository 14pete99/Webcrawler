"""Tests for app.config module."""

import pytest

from app.config import Settings, get_settings


class TestSettings:
    def test_default_values(self):
        s = Settings()
        assert s.crawl4ai_api == "http://localhost:11235"
        assert s.default_output_dir == "./output"
        assert s.profiles_dir == "data/profiles"
        assert s.sessions_dir == "data/sessions"
        assert s.captcha_api_key is None
        assert s.captcha_provider == "2captcha"

    def test_env_prefix(self):
        assert Settings.model_config["env_prefix"] == "CRAWLER_"


class TestGetSettings:
    def test_returns_settings_instance(self):
        s = get_settings()
        assert isinstance(s, Settings)

    def test_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
