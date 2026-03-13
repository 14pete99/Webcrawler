"""Wrapper for the crawl4ai Docker API."""

from __future__ import annotations

import base64
import json
import re
import uuid
from pathlib import Path
from urllib.parse import urljoin

import httpx

from app.models.crawl import ImageInfo
from app.models.extraction import ExtractionConfig
from app.services.image_compliance import enforce_compliance
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
    extraction: ExtractionConfig | None = None,
    cookies: list[dict] | None = None,
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

        # Combine pre-load JS and behavior scripts into a single injection.
        # Behavior scripts are wrapped in a setTimeout so they execute post-load
        # while the pre-load patches (fingerprint spoofing) run immediately.
        js_parts: list[str] = []
        if stealth.js_injection:
            js_parts.append(stealth.js_injection)
        if stealth.behavior_scripts:
            # Wrap each behavior script in setTimeout to run after page settles
            for script in stealth.behavior_scripts:
                js_parts.append(
                    f"setTimeout(function() {{ {script} }}, 2000);"
                )
            # Allow extra time for behavior scripts to complete
            crawler_params["delay_before_return_html"] = 5.0

        if js_parts:
            crawler_params["js_code"] = "\n".join(js_parts)

        # Geo consistency: set browser timezone/locale
        if stealth.geo_profile:
            browser_params["timezone_id"] = stealth.geo_profile.timezone
            browser_params["locale"] = stealth.geo_profile.locale

    # Extraction strategy configuration
    if extraction:
        if extraction.wait_for_selector:
            crawler_params["wait_for"] = f"css:{extraction.wait_for_selector}"
        if extraction.delay_before_extract is not None:
            crawler_params["delay_before_return_html"] = extraction.delay_before_extract

        # Pre-extraction page interactions (click tabs, expand, scroll, etc.)
        if extraction.pre_actions:
            action_js_parts: list[str] = []
            cumulative_delay = 0
            for act in extraction.pre_actions:
                if act.action == "click" and act.selector:
                    action_js_parts.append(
                        f"setTimeout(function() {{"
                        f" var el = document.querySelector('{act.selector}');"
                        f" if (el) el.click();"
                        f"}}, {cumulative_delay});"
                    )
                elif act.action == "wait" and act.selector:
                    # wait-for-selector is a polling wait
                    action_js_parts.append(
                        f"setTimeout(function() {{"
                        f" (function poll() {{"
                        f"   if (!document.querySelector('{act.selector}')) setTimeout(poll, 200);"
                        f" }})();"
                        f"}}, {cumulative_delay});"
                    )
                elif act.action == "scroll":
                    action_js_parts.append(
                        f"setTimeout(function() {{"
                        f" window.scrollTo(0, document.body.scrollHeight);"
                        f"}}, {cumulative_delay});"
                    )
                elif act.action == "js" and act.value:
                    action_js_parts.append(
                        f"setTimeout(function() {{ {act.value} }}, {cumulative_delay});"
                    )
                cumulative_delay += act.wait_after

            if action_js_parts:
                actions_js = "\n".join(action_js_parts)
                existing_js = crawler_params.get("js_code", "")
                crawler_params["js_code"] = (
                    existing_js + "\n" + actions_js if existing_js else actions_js
                )
                # Ensure enough delay for all actions to complete
                min_delay = cumulative_delay / 1000.0 + 2.0
                current_delay = crawler_params.get("delay_before_return_html", 0)
                if current_delay < min_delay:
                    crawler_params["delay_before_return_html"] = min_delay

        if extraction.strategy == "css" and extraction.selectors:
            crawler_params["extraction_strategy"] = {
                "type": "CssExtractionStrategy",
                "params": {
                    "schema": {
                        s.name: {
                            "selector": s.selector,
                            "type": "attribute" if s.attribute else "text",
                            **({"attribute": s.attribute} if s.attribute else {}),
                            "multiple": s.multiple,
                        }
                        for s in extraction.selectors
                    }
                },
            }
        elif extraction.strategy == "json-css" and extraction.schema_:
            crawler_params["extraction_strategy"] = {
                "type": "JsonCssExtractionStrategy",
                "params": {
                    "schema": {
                        "baseSelector": extraction.schema_.base_selector,
                        "fields": [
                            {
                                "name": f.name,
                                "selector": f.selector,
                                "type": "attribute" if f.attribute else "text",
                                **({"attribute": f.attribute} if f.attribute else {}),
                            }
                            for f in extraction.schema_.fields
                        ],
                    }
                },
            }

    if cookies:
        browser_params["cookies"] = cookies

    payload: dict = {
        "urls": [url],
        "browser_config": {"type": "BrowserConfig", "params": browser_params},
        "crawler_config": {"type": "CrawlerRunConfig", "params": crawler_params},
    }
    if session_id:
        payload["session_id"] = session_id

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(f"{api_base}/crawl", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 500:
                # crawl4ai internal error — return a structured error
                # instead of crashing the entire CLI
                return {
                    "success": False,
                    "images": [],
                    "screenshot_path": None,
                    "errors": [
                        f"crawl4ai returned 500: {exc.response.text[:200]}"
                    ],
                }
            raise
        data = resp.json()

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
            if session_id:
                retry_payload["session_id"] = session_id

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
    screenshot_tiles: list[str] | None = None
    page_html: str | None = None
    page_markdown: str | None = None
    extracted_content: list[dict] | dict | None = None
    page_links: list[dict] | None = None

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
            # Enforce Claude Code image limits (20 MB / 8000px)
            compliant = enforce_compliance(ss_path)
            screenshot_path = str(compliant[0])
            if len(compliant) > 1:
                screenshot_tiles = [str(p) for p in compliant]

        # Extraction data (HTML, markdown, extracted content, links)
        if extraction:
            if extraction.include_html and result.get("html"):
                page_html = result["html"]
            if extraction.include_markdown and result.get("markdown"):
                md = result["markdown"]
                if isinstance(md, dict):
                    # crawl4ai returns markdown as a dict with sub-fields;
                    # prefer markdown_with_citations, fall back to raw_markdown
                    page_markdown = (
                        md.get("markdown_with_citations")
                        or md.get("raw_markdown")
                        or ""
                    )
                else:
                    page_markdown = md
            if extraction.include_links:
                links_data = result.get("links", {})
                internal = links_data.get("internal", [])
                external = links_data.get("external", [])
                page_links = internal + external

            raw_extracted = result.get("extracted_content")
            if raw_extracted:
                if isinstance(raw_extracted, str):
                    try:
                        extracted_content = json.loads(raw_extracted)
                    except (json.JSONDecodeError, ValueError):
                        extracted_content = {"raw": raw_extracted}
                else:
                    extracted_content = raw_extracted

            # Regex extraction (post-process on our side)
            if extraction.strategy == "regex" and extraction.patterns:
                html_for_regex = result.get("html", "")
                if html_for_regex:
                    regex_results = {}
                    for name, pattern in extraction.patterns.items():
                        regex_results[name] = re.findall(pattern, html_for_regex)
                    extracted_content = regex_results

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

    result_dict = {
        "success": len(errors) == 0,
        "images": all_images,
        "screenshot_path": screenshot_path,
        "errors": errors,
    }
    if screenshot_tiles:
        result_dict["screenshot_tiles"] = screenshot_tiles
    if extracted_content is not None:
        result_dict["extracted_data"] = extracted_content
    if page_markdown is not None:
        result_dict["markdown"] = page_markdown
    if page_html is not None:
        result_dict["html"] = page_html
    if page_links is not None:
        result_dict["links"] = page_links
    return result_dict
