"""Tests for app.stealth.cookies module."""

import pytest

from app.stealth.cookies import cookie_consent_js, seed_storage_js


class TestCookieConsentJs:
    def test_returns_string(self):
        js = cookie_consent_js()
        assert isinstance(js, str)

    def test_contains_onetrust(self):
        js = cookie_consent_js()
        assert "onetrust-accept-btn-handler" in js

    def test_contains_cookiebot(self):
        js = cookie_consent_js()
        assert "CybotCookiebotDialog" in js

    def test_contains_mutation_observer(self):
        js = cookie_consent_js()
        assert "MutationObserver" in js

    def test_contains_timeout(self):
        js = cookie_consent_js()
        assert "setTimeout" in js


class TestSeedStorageJs:
    def test_empty_inputs(self):
        js = seed_storage_js()
        assert "(function() {" in js
        assert "})();" in js

    def test_local_storage_seeding(self):
        js = seed_storage_js(local_storage={"key1": "value1"})
        assert "localStorage.setItem('key1', 'value1')" in js

    def test_session_storage_seeding(self):
        js = seed_storage_js(session_storage={"sk": "sv"})
        assert "sessionStorage.setItem('sk', 'sv')" in js

    def test_both_storages(self):
        js = seed_storage_js(
            local_storage={"lk": "lv"},
            session_storage={"sk": "sv"},
        )
        assert "localStorage" in js
        assert "sessionStorage" in js

    def test_special_characters_escaped(self):
        js = seed_storage_js(local_storage={"it's": "a\\b"})
        assert "\\'" in js
        assert "\\\\" in js

    def test_try_catch_wrapping(self):
        js = seed_storage_js(local_storage={"k": "v"})
        assert "try {" in js
        assert "catch(e)" in js
