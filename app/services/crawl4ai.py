"""Wrapper for the crawl4ai Docker API."""

from __future__ import annotations

import base64
import uuid
from pathlib import Path
from urllib.parse import urljoin

import httpx

from app.models.crawl import ImageInfo
from app.stealth.pipeline import StealthContext


async def crawl_url(
    url: str,
    api_base: str = "http://localhost:11235",
    *,
    screenshot: bool = False,
    stealth: StealthContext | None = None,
    proxy: str | None = None,
    session_id: str | None = None,
    output_dir: Path | None = None,
    timeout: float = 120,
    captcha_solver: object | None = None,
    cloudflare_bypass: bool = False,
) -> dict:
    """Submit a crawl request to crawl4ai and return parsed results.

    Args:
        url: URL to crawl.
        api_base: crawl4ai API base URL.
        screenshot: Capture a rendered screenshot.
        stealth: Assembled stealth context.
        proxy: Proxy URL for the browser.
        session_id: Reuse a persistent browser session.
        output_dir: Directory to save the screenshot (if requested).
        timeout: Request timeout in seconds.

    Returns:
        Dict with keys: success, images (list[ImageInfo]), screenshot_path, errors.
    """
    crawler_params: dict = {
        "cache_mode": "bypass",
        "wait_for_images": True,
        "exclude_external_images": False,
    }
    if screenshot:
        crawler_params["screenshot"] = True
        crawler_params["screenshot_wait_for"] = 2.0

    browser_params: dict = {"headless": True}
    if proxy:
        browser_params["proxy"] = proxy
    if stealth:
        if stealth.user_agent_info:
            browser_params["user_agent"] = stealth.user_agent_info["ua"]
        if stealth.viewport:
            w, h = stealth.viewport
            browser_params["viewport_width"] = w
            browser_params["viewport_height"] = h
        if stealth.js_injection:
            crawler_params["js_code"] = stealth.js_injection
        # Geo consistency: set browser timezone/locale
        if stealth.geo_profile:
            browser_params["timezone_id"] = stealth.geo_profile.timezone
            browser_params["locale"] = stealth.geo_profile.locale

    payload: dict = {
        "urls": [url],
        "browser_config": {"type": "BrowserConfig", "params": browser_params},
        "crawler_config": {"type": "CrawlerRunConfig", "params": crawler_params},
    }
    # Behavioral scripts require a session to persist the browser tab
    effective_session_id = session_id
    if stealth and stealth.behavior_scripts and not effective_session_id:
        effective_session_id = f"auto-{uuid.uuid4().hex[:8]}"

    if effective_session_id:
        payload["session_id"] = effective_session_id

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{api_base}/crawl", json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Execute behavioral simulation scripts post-load
        if stealth and stealth.behavior_scripts and effective_session_id:
            behavior_payload = {
                "urls": [url],
                "session_id": effective_session_id,
                "browser_config": {"type": "BrowserConfig", "params": browser_params},
                "crawler_config": {"type": "CrawlerRunConfig", "params": {
                    "js_code": stealth.behavior_scripts,
                    "wait_for_images": False,
                }},
            }
            try:
                await client.post(f"{api_base}/crawl", json=behavior_payload)
            except Exception:
                pass  # Behavioral simulation is best-effort

    # Cloudflare challenge retry logic
    if cloudflare_bypass:
        from app.stealth.cloudflare import (
            build_cf_bypass_config,
            detect_challenge_type,
            detect_cloudflare_challenge,
            turnstile_callback_js,
        )

        raw_results = data.get("results", data.get("result", []))
        if not isinstance(raw_results, list):
            raw_results = [raw_results]

        for _retry in range(2):  # Max 2 retries
            html_content = ""
            for r in raw_results:
                if r and r.get("html"):
                    html_content = r["html"]
                    break

            if not html_content or not detect_cloudflare_challenge(html_content):
                break

            challenge_type = detect_challenge_type(html_content)
            if not challenge_type:
                break

            cf_params = build_cf_bypass_config(challenge_type)
            retry_crawler_params = {**crawler_params, **cf_params}

            # For Turnstile challenges, try CAPTCHA solver if available
            if challenge_type == "turnstile" and captcha_solver:
                try:
                    import re

                    site_key_match = re.search(
                        r'data-sitekey=["\']([^"\']+)', html_content
                    )
                    if site_key_match:
                        token = await captcha_solver.solve_turnstile(
                            site_key_match.group(1), url
                        )
                        retry_crawler_params["js_code"] = (
                            crawler_params.get("js_code", "")
                            + "\n"
                            + turnstile_callback_js(token)
                        )
                except Exception:
                    pass  # Fall back to normal retry

            retry_payload = {
                "urls": [url],
                "browser_config": {"type": "BrowserConfig", "params": browser_params},
                "crawler_config": {"type": "CrawlerRunConfig", "params": retry_crawler_params},
            }
            if effective_session_id:
                retry_payload["session_id"] = effective_session_id

            async with httpx.AsyncClient(timeout=timeout) as retry_client:
                retry_resp = await retry_client.post(f"{api_base}/crawl", json=retry_payload)
                retry_resp.raise_for_status()
                data = retry_resp.json()

    # Parse results
    results = data.get("results", data.get("result", []))
    if not isinstance(results, list):
        results = [results]

    all_images: list[ImageInfo] = []
    errors: list[str] = []
    screenshot_path: str | None = None

    for result in results:
        if not result or not result.get("success"):
            errors.append(result.get("error", "unknown error") if result else "empty result")
            continue

        # Screenshot
        screenshot_b64 = result.get("screenshot")
        if screenshot_b64 and output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            ss_path = output_dir / "screenshot.png"
            ss_path.write_bytes(base64.b64decode(screenshot_b64))
            screenshot_path = str(ss_path)

        # Images
        media = result.get("media", {})
        for img in media.get("images", []):
            src = img.get("src", "")
            if not src or src.startswith("data:"):
                continue
            if not src.startswith(("http://", "https://")):
                src = urljoin(url, src)
            all_images.append(
                ImageInfo(
                    src=src,
                    alt=img.get("alt", ""),
                    score=img.get("score", 0.0),
                )
            )

    return {
        "success": len(errors) == 0,
        "images": all_images,
        "screenshot_path": screenshot_path,
        "errors": errors,
    }
