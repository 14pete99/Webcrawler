"""Tests for app.stealth.geo module."""

import pytest

from app.services.proxy import ProxyEntry
from app.stealth.geo import GeoProfile, _GEO_MAP, geo_override_js, match_geo_to_proxy


class TestMatchGeoToProxy:
    def test_known_country(self):
        entry = ProxyEntry(url="http://proxy:8080", country="US")
        geo = match_geo_to_proxy(entry)
        assert geo is not None
        assert geo.country_code == "US"
        assert geo.timezone == "America/New_York"

    def test_unknown_country(self):
        entry = ProxyEntry(url="http://proxy:8080", country="ZZ")
        assert match_geo_to_proxy(entry) is None

    def test_no_country(self):
        entry = ProxyEntry(url="http://proxy:8080", country=None)
        assert match_geo_to_proxy(entry) is None

    def test_case_insensitive(self):
        entry = ProxyEntry(url="http://proxy:8080", country="gb")
        geo = match_geo_to_proxy(entry)
        assert geo is not None
        assert geo.country_code == "GB"

    def test_german_profile(self):
        entry = ProxyEntry(url="http://proxy:8080", country="DE")
        geo = match_geo_to_proxy(entry)
        assert geo.locale == "de-DE"
        assert "de-DE" in geo.languages

    def test_japanese_profile(self):
        entry = ProxyEntry(url="http://proxy:8080", country="JP")
        geo = match_geo_to_proxy(entry)
        assert geo.timezone == "Asia/Tokyo"


class TestGeoOverrideJs:
    def test_returns_string(self):
        geo = GeoProfile("US", "America/New_York", "en-US", ["en-US", "en"])
        js = geo_override_js(geo)
        assert isinstance(js, str)

    def test_contains_locale(self):
        geo = _GEO_MAP["FR"]
        js = geo_override_js(geo)
        assert "fr-FR" in js

    def test_contains_timezone(self):
        geo = _GEO_MAP["JP"]
        js = geo_override_js(geo)
        assert "Asia/Tokyo" in js

    def test_contains_navigator_overrides(self):
        geo = _GEO_MAP["US"]
        js = geo_override_js(geo)
        assert "navigator" in js
        assert "language" in js
        assert "languages" in js

    def test_contains_timezone_offset(self):
        geo = _GEO_MAP["US"]
        js = geo_override_js(geo)
        assert "getTimezoneOffset" in js

    def test_contains_intl_override(self):
        geo = _GEO_MAP["DE"]
        js = geo_override_js(geo)
        assert "Intl.DateTimeFormat" in js


class TestGeoMapIntegrity:
    def test_map_not_empty(self):
        assert len(_GEO_MAP) > 0

    def test_all_entries_have_required_fields(self):
        for code, geo in _GEO_MAP.items():
            assert geo.country_code == code
            assert geo.timezone
            assert geo.locale
            assert len(geo.languages) > 0
