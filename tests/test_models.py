"""Tests for pydantic models."""

import pytest

from app.models.crawl import CrawlRequest, CrawlResponse, ImageInfo
from app.models.download import DownloadRequest, DownloadResponse, DownloadResult
from app.models.session import SessionInfo
from app.models.stealth import StealthConfig, StealthProfile


class TestImageInfo:
    def test_defaults(self):
        img = ImageInfo(src="https://example.com/img.jpg")
        assert img.src == "https://example.com/img.jpg"
        assert img.alt == ""
        assert img.score == 0.0


class TestCrawlRequest:
    def test_defaults(self):
        req = CrawlRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.screenshot is False
        assert req.download_images is True
        assert req.output_dir == "./output"

    def test_all_fields(self):
        req = CrawlRequest(
            url="https://example.com",
            screenshot=True,
            output_dir="/tmp/out",
            profile_id="stealth",
            proxy="http://p:8080",
        )
        assert req.screenshot is True
        assert req.output_dir == "/tmp/out"


class TestCrawlResponse:
    def test_defaults(self):
        resp = CrawlResponse(success=True, url="https://example.com")
        assert resp.images_found == 0
        assert resp.manifest == []
        assert resp.errors == []


class TestDownloadResult:
    def test_success(self):
        r = DownloadResult(src="https://img.com/a.jpg", file="/tmp/a.jpg")
        assert r.error is None

    def test_error(self):
        r = DownloadResult(src="https://img.com/a.jpg", error="404")
        assert r.file is None


class TestStealthConfig:
    def test_defaults(self):
        c = StealthConfig()
        assert c.user_agent == "random"
        assert c.headers == "realistic"
        assert c.js_injection is True
        assert c.viewport == "random"
        assert c.delay_min_ms == 1000
        assert c.delay_max_ms == 3000
        assert c.canvas_spoof is True
        assert c.mouse_simulation is False
        assert c.captcha_solving is False

    def test_validation_delay_min(self):
        with pytest.raises(Exception):
            StealthConfig(delay_min_ms=-1)


class TestStealthProfile:
    def test_defaults(self):
        p = StealthProfile(id="test")
        assert p.name == ""
        assert isinstance(p.config, StealthConfig)

    def test_with_custom_config(self):
        p = StealthProfile(
            id="custom",
            name="Custom",
            config=StealthConfig(delay_min_ms=500),
        )
        assert p.config.delay_min_ms == 500


class TestSessionInfo:
    def test_defaults(self):
        s = SessionInfo(id="s1")
        assert s.has_cookies is False
        assert s.cookie_count == 0
        assert s.fingerprint_seed is None
