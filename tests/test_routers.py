"""Tests for FastAPI routers and the main app."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.stealth import StealthConfig, StealthProfile


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestProfilesRouter:
    @pytest.fixture(autouse=True)
    def _mock_storage(self, tmp_path):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        with patch("app.storage.profiles._profiles_dir", return_value=profiles_dir):
            yield

    def test_list_profiles_empty(self, client):
        resp = client.get("/profiles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_profile(self, client):
        payload = {"id": "test", "name": "Test", "config": {}}
        resp = client.post("/profiles", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"] == "test"

    def test_get_profile(self, client):
        client.post("/profiles", json={"id": "p1", "name": "P1", "config": {}})
        resp = client.get("/profiles/p1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "p1"

    def test_get_profile_not_found(self, client):
        resp = client.get("/profiles/nonexistent")
        assert resp.status_code == 404

    def test_update_profile(self, client):
        client.post("/profiles", json={"id": "p1", "name": "V1", "config": {}})
        resp = client.put("/profiles/p1", json={"id": "p1", "name": "V2", "config": {}})
        assert resp.status_code == 200
        assert resp.json()["name"] == "V2"

    def test_delete_profile(self, client):
        client.post("/profiles", json={"id": "del", "name": "Del", "config": {}})
        resp = client.delete("/profiles/del")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_profile_not_found(self, client):
        resp = client.delete("/profiles/nonexistent")
        assert resp.status_code == 404


class TestSessionsRouter:
    @pytest.fixture(autouse=True)
    def _mock_storage(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        with patch("app.storage.sessions._sessions_dir", return_value=sessions_dir):
            yield

    def test_list_sessions_empty(self, client):
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_delete_session_not_found(self, client):
        resp = client.delete("/sessions/nonexistent")
        assert resp.status_code == 404
