"""Tests for app.stealth.behavior module."""

import pytest

from app.models.stealth import StealthConfig
from app.stealth.behavior import (
    build_behavior_script,
    generate_dwell_js,
    generate_keystroke_js,
    generate_mouse_js,
    generate_scroll_js,
)


class TestGenerateMouseJs:
    def test_returns_string(self):
        js = generate_mouse_js((1920, 1080))
        assert isinstance(js, str)

    def test_embeds_viewport_dimensions(self):
        js = generate_mouse_js((800, 600))
        assert "800" in js
        assert "600" in js

    def test_custom_duration(self):
        js = generate_mouse_js((1920, 1080), duration_s=5.0)
        assert "5.0" in js

    def test_contains_bezier(self):
        js = generate_mouse_js((1920, 1080))
        assert "bezier" in js

    def test_dispatches_mousemove(self):
        js = generate_mouse_js((1920, 1080))
        assert "mousemove" in js


class TestGenerateScrollJs:
    def test_returns_string(self):
        js = generate_scroll_js()
        assert isinstance(js, str)

    def test_custom_scroll_count(self):
        js = generate_scroll_js(scroll_count=5)
        assert "5" in js

    def test_contains_scrollby(self):
        js = generate_scroll_js()
        assert "scrollBy" in js

    def test_dispatches_wheel_event(self):
        js = generate_scroll_js()
        assert "WheelEvent" in js


class TestGenerateKeystrokeJs:
    def test_returns_string(self):
        js = generate_keystroke_js("hello")
        assert isinstance(js, str)

    def test_text_embedded(self):
        js = generate_keystroke_js("test input")
        assert "test input" in js

    def test_dispatches_key_events(self):
        js = generate_keystroke_js("a")
        assert "keydown" in js
        assert "keypress" in js
        assert "keyup" in js

    def test_special_chars_escaped(self):
        js = generate_keystroke_js('he said "hi"')
        assert isinstance(js, str)  # should not raise


class TestGenerateDwellJs:
    def test_returns_string(self):
        js = generate_dwell_js()
        assert isinstance(js, str)

    def test_custom_bounds(self):
        js = generate_dwell_js(min_s=1.0, max_s=5.0)
        assert "1.0" in js
        assert "5.0" in js

    def test_returns_promise(self):
        js = generate_dwell_js()
        assert "Promise" in js


class TestBuildBehaviorScript:
    def test_empty_config_returns_empty(self):
        config = StealthConfig()
        scripts = build_behavior_script(config, (1920, 1080))
        assert scripts == []

    def test_mouse_enabled(self):
        config = StealthConfig(mouse_simulation=True)
        scripts = build_behavior_script(config, (1920, 1080))
        assert len(scripts) == 1
        assert "mousemove" in scripts[0]

    def test_scroll_enabled(self):
        config = StealthConfig(scroll_simulation=True)
        scripts = build_behavior_script(config, (1920, 1080))
        assert len(scripts) == 1
        assert "scrollBy" in scripts[0]

    def test_dwell_enabled(self):
        config = StealthConfig(dwell_time=True)
        scripts = build_behavior_script(config, (1920, 1080))
        assert len(scripts) == 1
        assert "Promise" in scripts[0]

    def test_all_enabled(self):
        config = StealthConfig(
            mouse_simulation=True,
            scroll_simulation=True,
            dwell_time=True,
        )
        scripts = build_behavior_script(config, (1920, 1080))
        assert len(scripts) == 3

    def test_viewport_passed_to_mouse(self):
        config = StealthConfig(mouse_simulation=True)
        scripts = build_behavior_script(config, (800, 600))
        assert "800" in scripts[0]
