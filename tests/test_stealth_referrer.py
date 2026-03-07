"""Tests for app.stealth.referrer module."""

from unittest.mock import patch

import pytest

from app.stealth.referrer import build_referrer_chain, pick_referrer


class TestPickReferrer:
    def test_google_referrer(self):
        with patch("app.stealth.referrer.random") as mock_rng:
            mock_rng.random.return_value = 0.1  # < 0.6 → Google
            result = pick_referrer("https://example.com/page")
            assert "google.com/search" in result
            assert "example" in result

    def test_direct_referrer(self):
        with patch("app.stealth.referrer.random") as mock_rng:
            mock_rng.random.return_value = 0.7  # 0.6-0.8 → direct
            result = pick_referrer("https://example.com")
            assert result == ""

    def test_social_referrer(self):
        with patch("app.stealth.referrer.random") as mock_rng:
            mock_rng.random.return_value = 0.85  # 0.8-0.9 → social
            mock_rng.choice.return_value = "https://www.reddit.com/"
            result = pick_referrer("https://example.com")
            assert "reddit.com" in result

    def test_same_domain_referrer(self):
        with patch("app.stealth.referrer.random") as mock_rng:
            mock_rng.random.return_value = 0.95  # > 0.9 → same domain
            result = pick_referrer("https://example.com/deep/page")
            assert result == "https://example.com/"

    def test_returns_string(self):
        result = pick_referrer("https://example.com")
        assert isinstance(result, str)


class TestBuildReferrerChain:
    def test_returns_list(self):
        chain = build_referrer_chain("https://example.com")
        assert isinstance(chain, list)

    def test_depth_controls_length(self):
        with patch("app.stealth.referrer.pick_referrer", return_value="https://google.com/search?q=test"):
            chain = build_referrer_chain("https://example.com", depth=3)
            assert len(chain) == 3

    def test_empty_referrers_excluded(self):
        with patch("app.stealth.referrer.pick_referrer", return_value=""):
            chain = build_referrer_chain("https://example.com", depth=3)
            assert len(chain) == 0

    def test_default_depth_is_2(self):
        with patch("app.stealth.referrer.pick_referrer", return_value="https://ref.com"):
            chain = build_referrer_chain("https://example.com")
            assert len(chain) == 2
