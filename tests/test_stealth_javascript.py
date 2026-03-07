"""Tests for app.stealth.javascript module."""

import pytest

from app.stealth.javascript import ALL_PATCHES, build_js_injection, get_js_scripts


class TestGetJsScripts:
    def test_enabled_includes_base_patches(self):
        scripts = get_js_scripts(enabled=True)
        assert len(scripts) == len(ALL_PATCHES)

    def test_disabled_returns_empty(self):
        scripts = get_js_scripts(enabled=False)
        assert scripts == []

    def test_fingerprint_config_adds_scripts(self):
        fc = {
            "canvas_spoof": True,
            "webgl_spoof": True,
            "audio_spoof": True,
            "hardware_spoof": True,
            "font_mask": True,
            "fingerprint_seed": 42,
        }
        scripts = get_js_scripts(enabled=True, fingerprint_config=fc)
        assert len(scripts) > len(ALL_PATCHES)

    def test_fingerprint_only_canvas(self):
        fc = {"canvas_spoof": True, "fingerprint_seed": 42}
        scripts = get_js_scripts(enabled=False, fingerprint_config=fc)
        assert len(scripts) == 1
        assert "toDataURL" in scripts[0]

    def test_fingerprint_seed_none_generates_random(self):
        fc = {"canvas_spoof": True, "fingerprint_seed": None}
        scripts = get_js_scripts(enabled=False, fingerprint_config=fc)
        assert len(scripts) == 1

    def test_all_fingerprint_flags(self):
        fc = {
            "canvas_spoof": True,
            "webgl_spoof": True,
            "audio_spoof": True,
            "hardware_spoof": True,
            "font_mask": True,
            "fingerprint_seed": 100,
        }
        scripts = get_js_scripts(enabled=False, fingerprint_config=fc)
        assert len(scripts) == 5


class TestBuildJsInjection:
    def test_enabled_returns_string(self):
        result = build_js_injection(enabled=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_disabled_returns_none(self):
        result = build_js_injection(enabled=False)
        assert result is None

    def test_combines_all_patches(self):
        result = build_js_injection(enabled=True)
        assert "webdriver" in result
        assert "plugins" in result

    def test_with_fingerprint_config(self):
        fc = {"canvas_spoof": True, "fingerprint_seed": 42}
        result = build_js_injection(enabled=True, fingerprint_config=fc)
        assert "toDataURL" in result


class TestAllPatches:
    def test_patches_not_empty(self):
        assert len(ALL_PATCHES) > 0

    def test_webdriver_patch_present(self):
        combined = "\n".join(ALL_PATCHES)
        assert "webdriver" in combined

    def test_chrome_patch_present(self):
        combined = "\n".join(ALL_PATCHES)
        assert "window.chrome" in combined
