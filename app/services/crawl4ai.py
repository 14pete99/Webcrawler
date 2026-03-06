"""Wraps the crawl4ai Docker API."""

from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import urljoin

import httpx

from ..config import get_settings
from ..stealth.pipeline import StealthContext


async def crawl_url(
    url: str,
    stealth: StealthContext,
    *,
    screenshot: bool = False,
    proxy: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Submit a crawl request to the crawl4ai service and return the raw result dict."""
    settings = get_settings()

    params: dict = {
        "cache_mode": "bypass",
        "wait_for_images": True,
        "exclude_external_images": False,
    }
    if screenshot:
        params["screenshot"] = True
        params["screenshot_wait_for"] = 2.0

    # Inject stealth JS
    if stealth.js_scripts:
        params["js_code"] = stealth.js_scripts

    browser_params: dict = {
        "headless": True,
        "user_agent": stealth.user_agent,
        "viewport_width": stealth.viewport[0],
        "viewport_height": stealth.viewport[1],
    }
    if proxy:
        browser_params["proxy"] = proxy

    payload = {
        "urls": [url],
        "browser_config": {"type": "BrowserConfig", "params": browser_params},
        "crawler_config": {"type": "CrawlerRunConfig", "params": params},
    }
    if session_id:
        payload["session_id"] = session_id

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{settings.crawl4ai_api}/crawl", json=payload)
        resp.raise_for_status()
        return resp.json()


def extract_images(crawl_data: dict, base_url: str) -> list[dict]:
    """Parse crawl results and return a list of image info dicts."""
    results = crawl_data.get("results", crawl_data.get("result", []))
    if not isinstance(results, list):
        results = [results]

    images: list[dict] = []
    for result in results:
        if not result or not result.get("success"):
            continue
        media = result.get("media", {})
        for img in media.get("images", []):
            src = img.get("src", "")
            if not src or src.startswith("data:"):
                continue
            if not src.startswith(("http://", "https://")):
                src = urljoin(base_url, src)
            images.append({
                "src": src,
                "alt": img.get("alt", ""),
                "score": img.get("score", 0),
            })
    return images


def extract_screenshot(crawl_data: dict, output_dir: Path) -> str | None:
    """Save the screenshot from crawl results if present. Returns the path."""
    results = crawl_data.get("results", crawl_data.get("result", []))
    if not isinstance(results, list):
        results = [results]

    for result in results:
        if not result:
            continue
        screenshot_b64 = result.get("screenshot")
        if screenshot_b64:
            screenshot_path = output_dir / "screenshot.png"
            screenshot_path.write_bytes(base64.b64decode(screenshot_b64))
            return str(screenshot_path)
    return None
