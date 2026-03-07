"""E2E tests for crawl_images.py — the image crawler CLI.

These tests mock the crawl4ai API and image download HTTP calls so they
run without Docker. They exercise the full CLI flow end-to-end: argument
parsing, crawl request, image downloading, manifest writing, screenshot
saving, and proxy rotation.
"""

import base64
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Import the module under test
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
import crawl_images


# --- Fixtures ---


@pytest.fixture()
def output_dir(tmp_path):
    d = tmp_path / "output"
    d.mkdir()
    return d


def make_crawl_response(images=None, screenshot_b64=None, success=True, error=None):
    """Build a fake crawl4ai API response."""
    result = {"success": success}
    if error:
        result["error"] = error
    if success:
        result["media"] = {
            "images": images or []
        }
    if screenshot_b64:
        result["screenshot"] = screenshot_b64
    return {"results": [result]}


def make_image_response(content=b"\x89PNG\r\n", content_type="image/png", status=200):
    """Build a fake requests.Response for image download."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {"content-type": content_type}
    resp.iter_content = MagicMock(return_value=[content])
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


# --- Proxy helpers ---


class TestLoadProxies:
    def test_no_proxies(self):
        assert crawl_images.load_proxies(None, None) == []

    def test_single_proxy(self):
        result = crawl_images.load_proxies("http://proxy:8080", None)
        assert result == ["http://proxy:8080"]

    def test_proxy_file(self, tmp_path):
        pfile = tmp_path / "proxies.txt"
        pfile.write_text("http://p1:8080\n# comment\nhttp://p2:8080\n\n")
        result = crawl_images.load_proxies(None, str(pfile))
        assert result == ["http://p1:8080", "http://p2:8080"]

    def test_both_proxy_and_file(self, tmp_path):
        pfile = tmp_path / "proxies.txt"
        pfile.write_text("http://p2:8080\n")
        result = crawl_images.load_proxies("http://p1:8080", str(pfile))
        assert result == ["http://p1:8080", "http://p2:8080"]


class TestMakeProxyCycle:
    def test_empty_returns_none(self):
        assert crawl_images.make_proxy_cycle([]) is None

    def test_cycles_through_proxies(self):
        pool = crawl_images.make_proxy_cycle(["a", "b"])
        assert next(pool) == "a"
        assert next(pool) == "b"
        assert next(pool) == "a"


class TestGetProxyDict:
    def test_http_proxy(self):
        result = crawl_images.get_proxy_dict("http://host:8080")
        assert result == {"http": "http://host:8080", "https": "http://host:8080"}

    def test_socks_proxy(self):
        result = crawl_images.get_proxy_dict("socks5://host:1080")
        assert result == {"http": "socks5://host:1080", "https": "socks5://host:1080"}


# --- Crawl function ---


class TestCrawl:
    @patch("crawl_images.requests.post")
    def test_basic_crawl_request(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        crawl_images.crawl("https://example.com")

        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert payload["urls"] == ["https://example.com"]
        assert payload["crawler_config"]["params"]["cache_mode"] == "bypass"
        assert "screenshot" not in payload["crawler_config"]["params"]

    @patch("crawl_images.requests.post")
    def test_crawl_with_screenshot(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        crawl_images.crawl("https://example.com", screenshot=True)

        payload = mock_post.call_args[1]["json"]
        assert payload["crawler_config"]["params"]["screenshot"] is True

    @patch("crawl_images.requests.post")
    def test_crawl_with_proxy(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        crawl_images.crawl("https://example.com", proxy="http://proxy:8080")

        payload = mock_post.call_args[1]["json"]
        assert payload["browser_config"]["params"]["proxy"] == "http://proxy:8080"


# --- Image download ---


class TestDownloadImage:
    @patch("crawl_images.requests.get")
    def test_downloads_image_with_url_filename(self, mock_get, output_dir):
        mock_get.return_value = make_image_response(b"imgdata", "image/jpeg")

        result = crawl_images.download_image(
            "https://example.com/photos/cat.jpg", output_dir
        )

        assert result is not None
        saved = Path(result)
        assert saved.exists()
        assert saved.name == "cat.jpg"
        assert saved.read_bytes() == b"imgdata"

    @patch("crawl_images.requests.get")
    def test_generates_hash_filename_for_extensionless_url(self, mock_get, output_dir):
        mock_get.return_value = make_image_response(b"imgdata", "image/png")

        result = crawl_images.download_image(
            "https://example.com/image", output_dir
        )

        assert result is not None
        saved = Path(result)
        assert saved.exists()
        assert saved.suffix == ".png"
        # Should be a hex hash filename
        assert len(saved.stem) == 12

    @patch("crawl_images.requests.get")
    def test_jpeg_content_type_becomes_jpg_extension(self, mock_get, output_dir):
        mock_get.return_value = make_image_response(b"imgdata", "image/jpeg")

        result = crawl_images.download_image(
            "https://example.com/noext", output_dir
        )

        assert Path(result).suffix == ".jpg"

    @patch("crawl_images.requests.get")
    def test_avoids_overwriting_existing_files(self, mock_get, output_dir):
        # Pre-create the file
        (output_dir / "cat.jpg").write_bytes(b"original")

        mock_get.return_value = make_image_response(b"newdata", "image/jpeg")

        result = crawl_images.download_image(
            "https://example.com/cat.jpg", output_dir
        )

        saved = Path(result)
        assert saved.exists()
        assert saved.name != "cat.jpg"  # Should have a suffix
        assert saved.read_bytes() == b"newdata"
        # Original untouched
        assert (output_dir / "cat.jpg").read_bytes() == b"original"

    @patch("crawl_images.requests.get")
    def test_download_with_proxy(self, mock_get, output_dir):
        mock_get.return_value = make_image_response(b"data", "image/png")

        crawl_images.download_image(
            "https://example.com/img.png", output_dir, proxy="http://proxy:8080"
        )

        mock_get.assert_called_once()
        assert mock_get.call_args[1]["proxies"] == {
            "http": "http://proxy:8080",
            "https": "http://proxy:8080",
        }

    @patch("crawl_images.requests.get")
    def test_returns_none_on_download_failure(self, mock_get, output_dir):
        mock_get.side_effect = Exception("Connection refused")

        result = crawl_images.download_image(
            "https://example.com/img.png", output_dir
        )

        assert result is None


# --- Full CLI E2E flow ---


class TestMainE2E:
    @patch("crawl_images.requests.get")
    @patch("crawl_images.requests.post")
    def test_full_crawl_and_download_flow(self, mock_post, mock_get, tmp_path):
        """E2E: crawl returns images, images are downloaded, manifest is written."""
        out = tmp_path / "out"
        out.mkdir()

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(
            images=[
                {"src": "https://example.com/a.jpg", "alt": "Image A", "score": 5},
                {"src": "https://example.com/b.png", "alt": "Image B", "score": 3},
            ]
        )
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        mock_get.return_value = make_image_response(b"pixels", "image/jpeg")

        with patch("sys.argv", ["crawl_images.py", "https://example.com", "--output-dir", str(out)]):
            crawl_images.main()

        # Verify manifest
        manifest = json.loads((out / "images.json").read_text())
        assert len(manifest) == 2
        assert all("src" in entry for entry in manifest)
        assert all("file" in entry for entry in manifest)

    @patch("crawl_images.requests.get")
    @patch("crawl_images.requests.post")
    def test_screenshot_is_saved(self, mock_post, mock_get, tmp_path):
        """E2E: screenshot base64 data is decoded and saved to disk."""
        out = tmp_path / "out"
        out.mkdir()

        screenshot_data = b"fake screenshot png bytes"
        screenshot_b64 = base64.b64encode(screenshot_data).decode()

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(
            images=[], screenshot_b64=screenshot_b64
        )
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        with patch("sys.argv", ["crawl_images.py", "https://example.com", "--output-dir", str(out), "--screenshot"]):
            crawl_images.main()

        screenshot_path = out / "screenshot.png"
        assert screenshot_path.exists()
        assert screenshot_path.read_bytes() == screenshot_data

    @patch("crawl_images.requests.post")
    def test_handles_crawl_failure(self, mock_post, tmp_path):
        """E2E: crawl failure is handled gracefully without crashing."""
        out = tmp_path / "out"
        out.mkdir()

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(
            success=False, error="Timeout"
        )
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        with patch("sys.argv", ["crawl_images.py", "https://example.com", "--output-dir", str(out)]):
            crawl_images.main()

        # No manifest written since no images
        assert not (out / "images.json").exists()

    @patch("crawl_images.requests.get")
    @patch("crawl_images.requests.post")
    def test_skips_data_uri_images(self, mock_post, mock_get, tmp_path):
        """E2E: data: URIs are skipped, only http(s) images downloaded."""
        out = tmp_path / "out"
        out.mkdir()

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(
            images=[
                {"src": "data:image/png;base64,abc", "alt": "inline"},
                {"src": "https://example.com/real.jpg", "alt": "real"},
            ]
        )
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        mock_get.return_value = make_image_response(b"img", "image/jpeg")

        with patch("sys.argv", ["crawl_images.py", "https://example.com", "--output-dir", str(out)]):
            crawl_images.main()

        manifest = json.loads((out / "images.json").read_text())
        assert len(manifest) == 1
        assert manifest[0]["src"] == "https://example.com/real.jpg"

    @patch("crawl_images.requests.get")
    @patch("crawl_images.requests.post")
    def test_resolves_relative_urls(self, mock_post, mock_get, tmp_path):
        """E2E: relative image URLs are resolved against the crawled page URL."""
        out = tmp_path / "out"
        out.mkdir()

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(
            images=[{"src": "/images/photo.jpg", "alt": "relative"}]
        )
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        mock_get.return_value = make_image_response(b"img", "image/jpeg")

        with patch("sys.argv", ["crawl_images.py", "https://example.com/page", "--output-dir", str(out)]):
            crawl_images.main()

        manifest = json.loads((out / "images.json").read_text())
        assert manifest[0]["src"] == "https://example.com/images/photo.jpg"

    @patch("crawl_images.requests.get")
    @patch("crawl_images.requests.post")
    def test_proxy_rotation_across_downloads(self, mock_post, mock_get, tmp_path):
        """E2E: proxies rotate across image downloads."""
        out = tmp_path / "out"
        out.mkdir()

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(
            images=[
                {"src": "https://example.com/a.jpg", "alt": "A"},
                {"src": "https://example.com/b.jpg", "alt": "B"},
                {"src": "https://example.com/c.jpg", "alt": "C"},
            ]
        )
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        mock_get.return_value = make_image_response(b"img", "image/jpeg")

        proxy_file = tmp_path / "proxies.txt"
        proxy_file.write_text("http://p1:8080\nhttp://p2:8080\n")

        with patch("sys.argv", [
            "crawl_images.py", "https://example.com",
            "--output-dir", str(out),
            "--proxy-file", str(proxy_file),
        ]):
            crawl_images.main()

        # Verify proxy rotation: crawl uses p1, downloads use p2, p1, p2
        download_calls = mock_get.call_args_list
        proxies_used = [c[1].get("proxies", {}).get("http") for c in download_calls]
        assert proxies_used == ["http://p2:8080", "http://p1:8080", "http://p2:8080"]

    @patch("crawl_images.requests.post")
    def test_no_images_found(self, mock_post, tmp_path):
        """E2E: no images in crawl response is handled gracefully."""
        out = tmp_path / "out"
        out.mkdir()

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(images=[])
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        with patch("sys.argv", ["crawl_images.py", "https://example.com", "--output-dir", str(out)]):
            crawl_images.main()

        assert not (out / "images.json").exists()

    def test_cli_missing_url_exits_with_error(self):
        """E2E: running without a URL argument exits with error code 2."""
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "crawl_images.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    @patch("crawl_images.requests.get")
    @patch("crawl_images.requests.post")
    def test_output_dir_created_if_missing(self, mock_post, mock_get, tmp_path):
        """E2E: output directory is created automatically if it doesn't exist."""
        out = tmp_path / "nested" / "deep" / "output"

        crawl_resp = MagicMock()
        crawl_resp.json.return_value = make_crawl_response(
            images=[{"src": "https://example.com/img.png", "alt": "test"}]
        )
        crawl_resp.raise_for_status = MagicMock()
        mock_post.return_value = crawl_resp

        mock_get.return_value = make_image_response(b"img", "image/png")

        with patch("sys.argv", ["crawl_images.py", "https://example.com", "--output-dir", str(out)]):
            crawl_images.main()

        assert out.exists()
        assert (out / "images.json").exists()
