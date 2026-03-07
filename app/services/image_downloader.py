"""Async image downloader with stealth support."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.models.crawl import ImageInfo
from app.models.download import DownloadResult
from app.services.image_compliance import enforce_compliance
from app.stealth.delays import async_delay
from app.stealth.headers import build_image_headers
from app.stealth.pipeline import StealthContext


def _derive_filename(src: str, content_type: str | None) -> str:
    """Derive a filename from a URL, falling back to a hash."""
    parsed = urlparse(src)
    name = parsed.path.rsplit("/", 1)[-1] if "/" in parsed.path else ""
    if name and re.search(r"\.\w{2,5}$", name):
        return name
    ext = "png"
    if content_type:
        ext = content_type.split("/")[-1].split(";")[0].strip()
        if ext == "jpeg":
            ext = "jpg"
    return hashlib.md5(src.encode()).hexdigest()[:12] + f".{ext}"


def _unique_path(output_dir: Path, name: str) -> Path:
    """Return a path that doesn't collide with existing files."""
    dest = output_dir / name
    counter = 1
    while dest.exists():
        stem = dest.stem.rstrip("0123456789").rstrip("_")
        dest = output_dir / f"{stem}_{counter}{dest.suffix}"
        counter += 1
    return dest


async def download_image(
    src: str,
    output_dir: Path,
    *,
    client: httpx.AsyncClient,
    stealth: StealthContext | None = None,
    referer: str | None = None,
) -> DownloadResult:
    """Download a single image.

    Args:
        src: Image URL.
        output_dir: Directory to save to.
        client: Shared httpx async client (may carry cookies for session persistence).
        stealth: Stealth context for headers and delays.
        referer: Referer URL for the request headers.

    Returns:
        DownloadResult with file path or error.
    """
    try:
        headers = {}
        if stealth:
            headers = build_image_headers(
                stealth.user_agent_info,
                referer=referer,
                strategy="realistic",
            )
            await async_delay(stealth.delay_func)

        resp = await client.get(src, headers=headers)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type")
        name = _derive_filename(src, content_type)
        dest = _unique_path(output_dir, name)

        output_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)

        # Enforce Claude Code image limits (20 MB / 8000px max dimension)
        compliant_paths = enforce_compliance(dest)
        if len(compliant_paths) == 1:
            return DownloadResult(src=src, file=str(compliant_paths[0]))
        # Image was split into tiles — return first tile, extras attached
        return DownloadResult(
            src=src,
            file=str(compliant_paths[0]),
            extra_files=[str(p) for p in compliant_paths[1:]],
        )
    except Exception as e:
        return DownloadResult(src=src, error=str(e))


async def download_images(
    images: list[ImageInfo],
    output_dir: Path,
    *,
    stealth: StealthContext | None = None,
    proxy: str | None = None,
    referer: str | None = None,
    cookies: dict | None = None,
) -> list[DownloadResult]:
    """Download a list of images with stealth and proxy support.

    Args:
        images: List of ImageInfo objects.
        output_dir: Directory to save images.
        stealth: Stealth context.
        proxy: Proxy URL.
        referer: Referer URL for headers.
        cookies: Pre-loaded cookies for session persistence.

    Returns:
        List of DownloadResult objects.
    """
    from .http_client import create_stealth_client

    async with create_stealth_client(stealth, proxy=proxy) as client:
        results: list[DownloadResult] = []
        for img in images:
            result = await download_image(
                img.src,
                output_dir,
                client=client,
                stealth=stealth,
                referer=referer,
            )
            result.alt = img.alt
            results.append(result)
    return results
