"""Tests for app.stealth.fingerprint module."""

import pytest

from app.stealth.fingerprint import (
    _BASELINE_FONTS,
    _CORES_POOL,
    _GPU_POOL,
    _MEMORY_POOL,
    audio_spoof_js,
    canvas_spoof_js,
    font_mask_js,
    generate_fingerprint_seed,
    hardware_spoof_js,
    webgl_spoof_js,
)


class TestGenerateFingerprintSeed:
    def test_returns_int(self):
        seed = generate_fingerprint_seed()
        assert isinstance(seed, int)

    def test_in_valid_range(self):
        for _ in range(20):
            seed = generate_fingerprint_seed()
            assert 0 <= seed < 2**32

    def test_different_seeds_generated(self):
        seeds = {generate_fingerprint_seed() for _ in range(10)}
        assert len(seeds) > 1


class TestCanvasSpoofJs:
    def test_returns_string(self):
        js = canvas_spoof_js(42)
        assert isinstance(js, str)

    def test_contains_mulberry32(self):
        js = canvas_spoof_js(42)
        assert "mulberry32" in js

    def test_contains_toDataURL(self):
        js = canvas_spoof_js(42)
        assert "toDataURL" in js

    def test_contains_getImageData(self):
        js = canvas_spoof_js(42)
        assert "getImageData" in js

    def test_seed_embedded(self):
        js = canvas_spoof_js(12345)
        assert "12345" in js

    def test_different_seeds_produce_different_js(self):
        assert canvas_spoof_js(1) != canvas_spoof_js(2)


class TestWebglSpoofJs:
    def test_returns_string(self):
        js = webgl_spoof_js(42)
        assert isinstance(js, str)

    def test_seed_selects_gpu(self):
        for i, (vendor, renderer) in enumerate(_GPU_POOL):
            js = webgl_spoof_js(i)
            assert vendor in js
            assert renderer in js

    def test_wraps_around_gpu_pool(self):
        idx = len(_GPU_POOL) + 1
        js = webgl_spoof_js(idx)
        vendor, renderer = _GPU_POOL[idx % len(_GPU_POOL)]
        assert vendor in js

    def test_contains_extension_shuffle(self):
        js = webgl_spoof_js(42)
        assert "getSupportedExtensions" in js


class TestAudioSpoofJs:
    def test_returns_string(self):
        js = audio_spoof_js(42)
        assert isinstance(js, str)

    def test_contains_analyser_override(self):
        js = audio_spoof_js(42)
        assert "AnalyserNode" in js

    def test_contains_audiobuffer_override(self):
        js = audio_spoof_js(42)
        assert "AudioBuffer" in js

    def test_contains_seed(self):
        js = audio_spoof_js(99999)
        assert "99999" in js


class TestHardwareSpoofJs:
    def test_returns_string(self):
        js = hardware_spoof_js()
        assert isinstance(js, str)

    def test_explicit_cores_and_memory(self):
        js = hardware_spoof_js(cores=8, memory=16)
        assert "return 8;" in js
        assert "return 16;" in js

    def test_random_cores_from_pool(self):
        js = hardware_spoof_js()
        assert "hardwareConcurrency" in js

    def test_contains_device_memory(self):
        js = hardware_spoof_js()
        assert "deviceMemory" in js


class TestFontMaskJs:
    def test_returns_string(self):
        js = font_mask_js()
        assert isinstance(js, str)

    def test_contains_baseline_fonts(self):
        js = font_mask_js()
        for font in _BASELINE_FONTS[:5]:
            assert font in js

    def test_contains_fontfaceset(self):
        js = font_mask_js()
        assert "FontFaceSet" in js
