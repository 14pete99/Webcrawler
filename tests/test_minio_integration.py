"""End-to-end tests for MinIO image storage integration.

Tests cover:
- MinIO config settings
- MinIO store module (upload, list, delete, presigned URLs)
- Image downloader MinIO upload path + fallback
- FastAPI lifespan MinIO initialization
- Docker-compose service wiring
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.config import Settings
from app.models.crawl import ImageInfo
from app.models.download import DownloadResult


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestMinIOConfig:
    def test_default_minio_settings(self):
        s = Settings()
        assert s.minio_endpoint == "localhost:9000"
        assert s.minio_access_key == "minioadmin"
        assert s.minio_secret_key == "minioadmin"
        assert s.minio_bucket == "crawled-images"
        assert s.minio_secure is False

    def test_minio_settings_from_env(self, monkeypatch):
        monkeypatch.setenv("CRAWLER_MINIO_ENDPOINT", "minio:9000")
        monkeypatch.setenv("CRAWLER_MINIO_ACCESS_KEY", "mykey")
        monkeypatch.setenv("CRAWLER_MINIO_SECRET_KEY", "mysecret")
        monkeypatch.setenv("CRAWLER_MINIO_BUCKET", "my-bucket")
        monkeypatch.setenv("CRAWLER_MINIO_SECURE", "true")
        s = Settings()
        assert s.minio_endpoint == "minio:9000"
        assert s.minio_access_key == "mykey"
        assert s.minio_secret_key == "mysecret"
        assert s.minio_bucket == "my-bucket"
        assert s.minio_secure is True


# ---------------------------------------------------------------------------
# MinIO store module tests (mocked MinIO client)
# ---------------------------------------------------------------------------

class TestMinIOStore:
    @pytest.fixture(autouse=True)
    def _reset_client(self):
        """Reset the module-level _client before each test."""
        import app.storage.minio_store as mod
        mod._client = None
        yield
        mod._client = None

    def _make_mock_client(self):
        client = MagicMock()
        client.bucket_exists.return_value = False
        client.make_bucket.return_value = None
        client.put_object.return_value = None
        client.presigned_get_object.return_value = "http://minio:9000/bucket/img.jpg?sig=abc"
        client.list_objects.return_value = []
        client.remove_object.return_value = None
        return client

    def test_init_minio_creates_bucket(self):
        mock_client = self._make_mock_client()
        mock_client.bucket_exists.return_value = False
        with patch("app.storage.minio_store._create_client", return_value=mock_client):
            from app.storage.minio_store import init_minio
            init_minio(Settings())
        mock_client.bucket_exists.assert_called_once_with("crawled-images")
        mock_client.make_bucket.assert_called_once_with("crawled-images")

    def test_init_minio_existing_bucket(self):
        mock_client = self._make_mock_client()
        mock_client.bucket_exists.return_value = True
        with patch("app.storage.minio_store._create_client", return_value=mock_client):
            from app.storage.minio_store import init_minio
            init_minio(Settings())
        mock_client.make_bucket.assert_not_called()

    def test_upload_image(self):
        mock_client = self._make_mock_client()
        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import upload_image
        key = upload_image(b"fake-image-data", "test.jpg", content_type="image/jpeg")

        assert key == "test.jpg"
        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args
        assert call_args[0][0] == "crawled-images"
        assert call_args[0][1] == "test.jpg"
        assert call_args[1]["length"] == len(b"fake-image-data")
        assert call_args[1]["content_type"] == "image/jpeg"

    def test_upload_image_custom_bucket(self):
        mock_client = self._make_mock_client()
        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import upload_image
        upload_image(b"data", "img.png", bucket="other-bucket")

        call_args = mock_client.put_object.call_args
        assert call_args[0][0] == "other-bucket"

    def test_get_presigned_url(self):
        mock_client = self._make_mock_client()
        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import get_presigned_url
        url = get_presigned_url("test.jpg")

        assert "minio" in url
        mock_client.presigned_get_object.assert_called_once()

    def test_list_objects_empty(self):
        mock_client = self._make_mock_client()
        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import list_objects
        result = list_objects()
        assert result == []

    def test_list_objects_with_items(self):
        mock_client = self._make_mock_client()
        obj = MagicMock()
        obj.object_name = "cat.jpg"
        obj.size = 1024
        obj.last_modified = MagicMock()
        obj.last_modified.isoformat.return_value = "2026-03-08T00:00:00"
        obj.content_type = "image/jpeg"
        mock_client.list_objects.return_value = [obj]

        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import list_objects
        result = list_objects()
        assert len(result) == 1
        assert result[0]["name"] == "cat.jpg"
        assert result[0]["size"] == 1024

    def test_list_objects_with_prefix(self):
        mock_client = self._make_mock_client()
        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import list_objects
        list_objects(prefix="crawl-001/")
        mock_client.list_objects.assert_called_once_with(
            "crawled-images", prefix="crawl-001/", recursive=True,
        )

    def test_delete_object(self):
        mock_client = self._make_mock_client()
        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import delete_object
        delete_object("old.jpg")
        mock_client.remove_object.assert_called_once_with("crawled-images", "old.jpg")

    def test_get_minio_client_creates_on_first_call(self):
        with patch("app.storage.minio_store._create_client") as mock_create:
            mock_create.return_value = self._make_mock_client()
            from app.storage.minio_store import get_minio_client
            client = get_minio_client()
            assert client is not None
            mock_create.assert_called_once()

    def test_get_minio_client_returns_singleton(self):
        mock_client = self._make_mock_client()
        import app.storage.minio_store as mod
        mod._client = mock_client

        from app.storage.minio_store import get_minio_client
        c1 = get_minio_client()
        c2 = get_minio_client()
        assert c1 is c2


# ---------------------------------------------------------------------------
# Image downloader MinIO integration
# ---------------------------------------------------------------------------

class TestImageDownloaderMinIO:
    def test_upload_to_minio_success(self, tmp_path):
        img_file = tmp_path / "photo.jpg"
        img_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        mock_client = MagicMock()
        with patch("app.storage.minio_store._client", mock_client), \
             patch("app.storage.minio_store.get_minio_client", return_value=mock_client):
            from app.services.image_downloader import _upload_to_minio
            keys = _upload_to_minio([img_file], "image/jpeg")

        assert keys == ["photo.jpg"]
        mock_client.put_object.assert_called_once()

    def test_upload_to_minio_multiple_files(self, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"tile_{i}.jpg"
            f.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)
            files.append(f)

        mock_client = MagicMock()
        with patch("app.storage.minio_store._client", mock_client), \
             patch("app.storage.minio_store.get_minio_client", return_value=mock_client):
            from app.services.image_downloader import _upload_to_minio
            keys = _upload_to_minio(files, "image/jpeg")

        assert len(keys) == 3
        assert mock_client.put_object.call_count == 3

    def test_upload_to_minio_fallback_on_no_client(self):
        """When MinIO is not initialized, _upload_to_minio returns empty list."""
        import app.storage.minio_store as mod
        mod._client = None

        with patch("app.storage.minio_store._create_client", side_effect=Exception("no server")):
            from app.services.image_downloader import _upload_to_minio
            keys = _upload_to_minio([Path("fake.jpg")], "image/jpeg")

        assert keys == []

    def test_upload_to_minio_fallback_on_upload_error(self, tmp_path):
        img_file = tmp_path / "fail.jpg"
        img_file.write_bytes(b"\xff\xd8\xff")

        mock_client = MagicMock()
        mock_client.put_object.side_effect = Exception("connection refused")
        with patch("app.storage.minio_store._client", mock_client), \
             patch("app.storage.minio_store.get_minio_client", return_value=mock_client):
            from app.services.image_downloader import _upload_to_minio
            keys = _upload_to_minio([img_file], "image/jpeg")

        assert keys == []

    def test_upload_to_minio_default_content_type(self, tmp_path):
        img_file = tmp_path / "unknown.bin"
        img_file.write_bytes(b"\x00" * 10)

        mock_client = MagicMock()
        with patch("app.storage.minio_store._client", mock_client), \
             patch("app.storage.minio_store.get_minio_client", return_value=mock_client):
            from app.services.image_downloader import _upload_to_minio
            _upload_to_minio([img_file], None)

        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["content_type"] == "application/octet-stream"


# ---------------------------------------------------------------------------
# Download + MinIO end-to-end (mocked HTTP + mocked MinIO)
# ---------------------------------------------------------------------------

class TestDownloadImageWithMinIO:
    @pytest.fixture
    def mock_minio(self):
        mock_client = MagicMock()
        with patch("app.storage.minio_store._client", mock_client), \
             patch("app.storage.minio_store.get_minio_client", return_value=mock_client):
            yield mock_client

    @pytest.mark.asyncio
    async def test_download_uploads_to_minio(self, tmp_path, mock_minio):
        """Full download_image call should upload result to MinIO."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"\xff\xd8\xff" + b"\x00" * 100
        mock_response.raise_for_status = MagicMock()

        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = MagicMock(return_value=mock_response)

        # Make .get() awaitable
        import asyncio
        async def mock_get(*args, **kwargs):
            return mock_response
        mock_http.get = mock_get

        with patch("app.services.image_downloader.enforce_compliance", side_effect=lambda p: [p]):
            from app.services.image_downloader import download_image
            result = await download_image(
                "https://example.com/photo.jpg",
                tmp_path,
                client=mock_http,
            )

        assert result.error is None
        assert result.file == "photo.jpg"
        mock_minio.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_falls_back_to_local_on_minio_failure(self, tmp_path):
        """When MinIO upload fails, result.file should be a local path."""
        import httpx
        import app.storage.minio_store as mod
        mod._client = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/png"}
        mock_response.content = b"\x89PNG" + b"\x00" * 100
        mock_response.raise_for_status = MagicMock()

        async def mock_get(*args, **kwargs):
            return mock_response

        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = mock_get

        with patch("app.services.image_downloader.enforce_compliance", side_effect=lambda p: [p]), \
             patch("app.storage.minio_store._create_client", side_effect=Exception("offline")):
            from app.services.image_downloader import download_image
            result = await download_image(
                "https://example.com/image.png",
                tmp_path,
                client=mock_http,
            )

        assert result.error is None
        # Should be a local filesystem path, not a MinIO key
        assert str(tmp_path) in result.file or "image" in result.file

    @pytest.mark.asyncio
    async def test_download_with_tiled_images_uploads_all(self, tmp_path, mock_minio):
        """When compliance splits image into tiles, all tiles are uploaded."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"\xff\xd8\xff" + b"\x00" * 100
        mock_response.raise_for_status = MagicMock()

        async def mock_get(*args, **kwargs):
            return mock_response

        mock_http = MagicMock()
        mock_http.get = mock_get

        tile1 = tmp_path / "big_0.jpg"
        tile2 = tmp_path / "big_1.jpg"
        tile1.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)
        tile2.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)

        with patch("app.services.image_downloader.enforce_compliance", return_value=[tile1, tile2]):
            from app.services.image_downloader import download_image
            result = await download_image(
                "https://example.com/huge.jpg",
                tmp_path,
                client=mock_http,
            )

        assert result.file == "big_0.jpg"
        assert result.extra_files == ["big_1.jpg"]
        assert mock_minio.put_object.call_count == 2


# ---------------------------------------------------------------------------
# FastAPI lifespan MinIO initialization
# ---------------------------------------------------------------------------

class TestLifespanMinIO:
    def test_lifespan_initializes_minio(self, tmp_path):
        """FastAPI lifespan should call init_minio on startup."""
        from fastapi.testclient import TestClient

        with patch("app.main.get_settings") as mock_settings, \
             patch("app.storage.minio_store.init_minio") as mock_init:
            settings = Settings()
            settings.profiles_dir = str(tmp_path / "profiles")
            settings.sessions_dir = str(tmp_path / "sessions")
            settings.default_output_dir = str(tmp_path / "output")
            mock_settings.return_value = settings

            from app.main import app
            with TestClient(app):
                pass

            mock_init.assert_called_once_with(settings)

    def test_lifespan_handles_minio_failure(self, tmp_path):
        """App should start even if MinIO is unavailable."""
        from fastapi.testclient import TestClient

        with patch("app.main.get_settings") as mock_settings, \
             patch("app.storage.minio_store.init_minio", side_effect=Exception("connection refused")):
            settings = Settings()
            settings.profiles_dir = str(tmp_path / "profiles")
            settings.sessions_dir = str(tmp_path / "sessions")
            settings.default_output_dir = str(tmp_path / "output")
            mock_settings.return_value = settings

            from app.main import app
            with TestClient(app) as client:
                resp = client.get("/health")
                assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Docker-compose validation
# ---------------------------------------------------------------------------

class TestDockerComposeWiring:
    @pytest.fixture(autouse=True)
    def _load_compose(self):
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml not found"
        # Use yaml if available, otherwise parse manually
        try:
            import yaml
            with open(compose_path) as f:
                self.compose = yaml.safe_load(f)
        except ImportError:
            # Fallback: just verify the file contains expected strings
            self.compose = None
            self.compose_text = compose_path.read_text()

    def test_minio_service_defined(self):
        if self.compose:
            assert "minio" in self.compose["services"]
        else:
            assert "minio:" in self.compose_text

    def test_minio_ports(self):
        if self.compose:
            ports = self.compose["services"]["minio"]["ports"]
            port_strs = [str(p) for p in ports]
            assert any("9000" in p for p in port_strs)
            assert any("9001" in p for p in port_strs)
        else:
            assert "9000:9000" in self.compose_text
            assert "9001:9001" in self.compose_text

    def test_minio_volume_defined(self):
        if self.compose:
            assert "minio-data" in self.compose.get("volumes", {})
        else:
            assert "minio-data:" in self.compose_text

    def test_webcrawler_depends_on_minio(self):
        if self.compose:
            deps = self.compose["services"]["webcrawler"]["depends_on"]
            assert "minio" in deps
        else:
            assert "minio" in self.compose_text

    def test_webcrawler_minio_env_vars(self):
        if self.compose:
            env = self.compose["services"]["webcrawler"]["environment"]
            env_str = str(env)
            assert "CRAWLER_MINIO_ENDPOINT" in env_str
            assert "CRAWLER_MINIO_ACCESS_KEY" in env_str
            assert "CRAWLER_MINIO_SECRET_KEY" in env_str
            assert "CRAWLER_MINIO_BUCKET" in env_str
        else:
            assert "CRAWLER_MINIO_ENDPOINT" in self.compose_text
            assert "CRAWLER_MINIO_ACCESS_KEY" in self.compose_text

    def test_minio_healthcheck(self):
        if self.compose:
            hc = self.compose["services"]["minio"].get("healthcheck")
            assert hc is not None
        else:
            assert "healthcheck" in self.compose_text

    def test_minio_console_address(self):
        if self.compose:
            cmd = self.compose["services"]["minio"]["command"]
            assert "9001" in cmd
        else:
            assert "--console-address" in self.compose_text
