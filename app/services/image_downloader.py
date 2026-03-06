"""Async image downloads with stealth headers and delays."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..stealth.delays import async_delay
from ..stealth.pipeline import StealthContext


async def download_image(
    src: str,
    output_dir: Path,
    stealth: StealthContext,
    *,
    proxy: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Download a single image and return the local file path, or ``None`` on failure."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=30,
            headers=stealth.headers,
            proxy=proxy,
        )
    try:
        # Apply stealth delay before downloading
        await async_delay(stealth.delay_fn)

        resp = await client.get(src, headers=stealth.headers)
        resp.raise_for_status()

        parsed = urlparse(src)
        name = parsed.path.rsplit("/", 1)[-1] if "/" in parsed.path else ""
        if not name or not re.search(r"\.\w{2,5}$", name):
            ext = resp.headers.get("content-type", "image/png").split("/")[-1]
            ext = ext.split(";")[0].strip()
            if ext == "jpeg":
                ext = "jpg"
            name = hashlib.md5(src.encode()).hexdigest()[:12] + f".{ext}"

        dest = output_dir / name
        counter = 1
        while dest.exists():
            stem = dest.stem.rstrip("0123456789").rstrip("_")
            dest = output_dir / f"{stem}_{counter}{dest.suffix}"
            counter += 1

        dest.write_bytes(resp.content)
        return str(dest)
    except Exception:
        return None
    finally:
        if own_client:
            await client.aclose()


async def download_images(
    images: list[dict],
    output_dir: Path,
    stealth: StealthContext,
    *,
    proxy: str | None = None,
) -> tuple[list[dict], list[str]]:
    """Download all images and return (manifest, errors)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    errors: list[str] = []

    async with httpx.AsyncClient(
        timeout=30,
        headers=stealth.headers,
        proxy=proxy,
    ) as client:
        for img in images:
            src = img["src"]
            path = await download_image(src, output_dir, stealth, client=client)
            if path:
                manifest.append({"file": path, "alt": img.get("alt", ""), "src": src})
            else:
                errors.append(f"Failed to download {src}")

    return manifest, errors
