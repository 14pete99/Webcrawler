"""Tests for app.storage.profiles and app.storage.sessions modules."""

import json
from unittest.mock import patch

import pytest

from app.models.stealth import StealthConfig, StealthProfile


class TestProfileStorage:
    @pytest.fixture(autouse=True)
    def _use_tmp_dir(self, tmp_path):
        """Redirect profiles storage to tmp_path."""
        self.profiles_dir = tmp_path / "profiles"
        self.profiles_dir.mkdir()
        with patch("app.storage.profiles._profiles_dir", return_value=self.profiles_dir):
            yield

    def test_list_profiles_empty(self):
        from app.storage.profiles import list_profiles
        assert list_profiles() == []

    def test_save_and_get_profile(self):
        from app.storage.profiles import get_profile, save_profile
        profile = StealthProfile(id="test", name="Test Profile")
        save_profile(profile)
        loaded = get_profile("test")
        assert loaded is not None
        assert loaded.id == "test"
        assert loaded.name == "Test Profile"

    def test_get_nonexistent_profile(self):
        from app.storage.profiles import get_profile
        assert get_profile("nonexistent") is None

    def test_list_profiles_returns_saved(self):
        from app.storage.profiles import list_profiles, save_profile
        save_profile(StealthProfile(id="a", name="A"))
        save_profile(StealthProfile(id="b", name="B"))
        profiles = list_profiles()
        assert len(profiles) == 2
        ids = {p.id for p in profiles}
        assert ids == {"a", "b"}

    def test_delete_profile(self):
        from app.storage.profiles import delete_profile, get_profile, save_profile
        save_profile(StealthProfile(id="del-me", name="Delete Me"))
        assert delete_profile("del-me") is True
        assert get_profile("del-me") is None

    def test_delete_nonexistent_returns_false(self):
        from app.storage.profiles import delete_profile
        assert delete_profile("nope") is False

    def test_save_profile_with_config(self):
        from app.storage.profiles import get_profile, save_profile
        config = StealthConfig(delay_min_ms=500, mouse_simulation=True)
        profile = StealthProfile(id="custom", name="Custom", config=config)
        save_profile(profile)
        loaded = get_profile("custom")
        assert loaded.config.delay_min_ms == 500
        assert loaded.config.mouse_simulation is True

    def test_overwrite_profile(self):
        from app.storage.profiles import get_profile, save_profile
        save_profile(StealthProfile(id="x", name="V1"))
        save_profile(StealthProfile(id="x", name="V2"))
        loaded = get_profile("x")
        assert loaded.name == "V2"


class TestSessionStorage:
    @pytest.fixture(autouse=True)
    def _use_tmp_dir(self, tmp_path):
        """Redirect sessions storage to tmp_path."""
        self.sessions_dir = tmp_path / "sessions"
        self.sessions_dir.mkdir()
        with patch("app.storage.sessions._sessions_dir", return_value=self.sessions_dir):
            yield

    def test_list_sessions_empty(self):
        from app.storage.sessions import list_sessions
        assert list_sessions() == []

    def test_save_and_get_cookies(self):
        from app.storage.sessions import get_session_cookies, save_session_cookies
        cookies = [{"name": "session", "value": "abc123"}]
        save_session_cookies("sess1", cookies)
        loaded = get_session_cookies("sess1")
        assert loaded == cookies

    def test_get_nonexistent_session(self):
        from app.storage.sessions import get_session_cookies
        assert get_session_cookies("nonexistent") is None

    def test_save_session_profile(self):
        from app.storage.sessions import get_session_profile, save_session_profile
        save_session_profile(
            "sess2",
            cookies=[{"name": "c1", "value": "v1"}],
            local_storage={"key": "val"},
            fingerprint_seed=42,
            last_user_agent="Mozilla/5.0",
        )
        profile = get_session_profile("sess2")
        assert profile is not None
        assert profile["cookies"] == [{"name": "c1", "value": "v1"}]
        assert profile["local_storage"] == {"key": "val"}
        assert profile["fingerprint_seed"] == 42
        assert profile["last_user_agent"] == "Mozilla/5.0"

    def test_save_session_profile_partial_update(self):
        from app.storage.sessions import get_session_profile, save_session_profile
        save_session_profile("sess3", cookies=[{"name": "c", "value": "v"}])
        save_session_profile("sess3", fingerprint_seed=99)
        profile = get_session_profile("sess3")
        assert profile["cookies"] == [{"name": "c", "value": "v"}]
        assert profile["fingerprint_seed"] == 99

    def test_delete_session(self):
        from app.storage.sessions import delete_session, get_session_profile, save_session_cookies
        save_session_cookies("del-me", [])
        assert delete_session("del-me") is True
        assert get_session_profile("del-me") is None

    def test_delete_nonexistent_returns_false(self):
        from app.storage.sessions import delete_session
        assert delete_session("nope") is False

    def test_list_sessions_with_data(self):
        from app.storage.sessions import list_sessions, save_session_profile
        save_session_profile("s1", cookies=[{"name": "a", "value": "b"}], fingerprint_seed=10)
        save_session_profile("s2", local_storage={"k": "v"})
        sessions = list_sessions()
        assert len(sessions) == 2
        ids = {s.id for s in sessions}
        assert ids == {"s1", "s2"}
        s1 = next(s for s in sessions if s.id == "s1")
        assert s1.has_cookies is True
        assert s1.cookie_count == 1
        assert s1.fingerprint_seed == 10
