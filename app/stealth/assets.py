"""Asset simulation — fetch CSS/JS to mimic real browser loading."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from app.stealth.delays import async_delay
from app.stealth.pipeline import StealthContext


def discover_page_assets(html: str, base_url: str) -> list[str]:
    """Extract stylesheet and script URLs from HTML.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative paths.

    Returns:
        List of absolute asset URLs.
    """
    urls: list[str] = []

    # Stylesheets: <link rel="stylesheet" href="...">
    for match in re.finditer(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    ):
        urls.append(urljoin(base_url, match.group(1)))

    # Also match href before rel
    for match in re.finditer(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\']',
        html,
        re.IGNORECASE,
    ):
        url = urljoin(base_url, match.group(1))
        if url not in urls:
            urls.append(url)

    # Scripts: <script src="...">
    for match in re.finditer(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    ):
        urls.append(urljoin(base_url, match.group(1)))

    return urls


async def fetch_assets(
    urls: list[str],
    client: object,
    stealth: StealthContext | None = None,
    max_assets: int = 10,
) -> None:
    """Fire requests for page assets to simulate real browser loading.

    Responses are discarded — we only want the traffic pattern.

    Args:
        urls: List of asset URLs to fetch.
        client: HTTP client (httpx.AsyncClient or compatible).
        stealth: Stealth context for delays.
        max_assets: Maximum number of assets to fetch.
    """
    for url in urls[:max_assets]:
        try:
            delay_func = stealth.delay_func if stealth else None
            await async_delay(delay_func)
            await client.get(url)  # type: ignore[union-attr]
        except Exception:
            pass  # Best-effort — we don't need the responses
