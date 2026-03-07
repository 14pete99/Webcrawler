"""Tests for app.stealth.viewport module."""

import pytest

from app.stealth.viewport import _VIEWPORT_POOL, pick_viewport


class TestPickViewport:
    def test_none_returns_none(self):
        assert pick_viewport(None) is None

    def test_random_returns_valid_tuple(self):
        result = pick_viewport("random")
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, int) for v in result)

    def test_preset_name_returns_exact_match(self):
        result = pick_viewport("1920x1080")
        assert result == (1920, 1080)

    def test_all_presets_return_correct_values(self):
        for name, expected in _VIEWPORT_POOL.items():
            assert pick_viewport(name) == expected

    def test_custom_wxh_format(self):
        result = pick_viewport("800x600")
        assert result == (800, 600)

    def test_custom_wxh_case_insensitive(self):
        result = pick_viewport("800X600")
        assert result == (800, 600)

    def test_invalid_format_falls_back_to_random(self):
        result = pick_viewport("invalid")
        assert result is not None
        assert result in _VIEWPORT_POOL.values()

    def test_pool_has_desktop_and_mobile_sizes(self):
        has_desktop = any(w >= 1000 for w, h in _VIEWPORT_POOL.values())
        has_mobile = any(w < 500 for w, h in _VIEWPORT_POOL.values())
        assert has_desktop
        assert has_mobile
