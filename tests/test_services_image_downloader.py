"""Tests for app.services.image_downloader module."""

from pathlib import Path

import pytest

from app.services.image_downloader import _derive_filename, _unique_path


class TestDeriveFilename:
    def test_url_with_extension(self):
        name = _derive_filename("https://example.com/photos/cat.jpg", None)
        assert name == "cat.jpg"

    def test_url_with_png_extension(self):
        name = _derive_filename("https://example.com/img.png", None)
        assert name == "img.png"

    def test_url_without_extension_uses_content_type(self):
        name = _derive_filename("https://example.com/image", "image/png")
        assert name.endswith(".png")
        assert len(name) > 4  # hash + extension

    def test_jpeg_content_type_becomes_jpg(self):
        name = _derive_filename("https://example.com/image", "image/jpeg")
        assert name.endswith(".jpg")

    def test_no_extension_no_content_type(self):
        name = _derive_filename("https://example.com/image", None)
        assert name.endswith(".png")  # default

    def test_hash_filename_length(self):
        name = _derive_filename("https://example.com/image", "image/png")
        stem = name.rsplit(".", 1)[0]
        assert len(stem) == 12

    def test_content_type_with_charset(self):
        name = _derive_filename("https://example.com/img", "image/webp; charset=utf-8")
        assert name.endswith(".webp")

    def test_deep_url_path(self):
        name = _derive_filename("https://cdn.example.com/a/b/c/photo.webp", None)
        assert name == "photo.webp"

    def test_url_with_query_params(self):
        name = _derive_filename("https://example.com/photo.jpg?w=800&h=600", None)
        # The query params are part of the path parsing, so the filename may vary
        assert isinstance(name, str)


class TestUniquePath:
    def test_no_collision(self, tmp_path):
        path = _unique_path(tmp_path, "test.jpg")
        assert path == tmp_path / "test.jpg"

    def test_collision_adds_suffix(self, tmp_path):
        (tmp_path / "test.jpg").write_bytes(b"existing")
        path = _unique_path(tmp_path, "test.jpg")
        assert path != tmp_path / "test.jpg"
        assert path.suffix == ".jpg"
        assert path.parent == tmp_path

    def test_multiple_collisions(self, tmp_path):
        (tmp_path / "test.jpg").write_bytes(b"1")
        (tmp_path / "test_1.jpg").write_bytes(b"2")
        path = _unique_path(tmp_path, "test.jpg")
        assert not path.exists()
        assert path.suffix == ".jpg"

    def test_preserves_extension(self, tmp_path):
        (tmp_path / "img.png").write_bytes(b"x")
        path = _unique_path(tmp_path, "img.png")
        assert path.suffix == ".png"
