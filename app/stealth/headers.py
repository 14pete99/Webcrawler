"""Realistic HTTP header generation matched to user agent."""

from __future__ import annotations


def generate_headers(
    user_agent: str,
    strategy: str | None = "realistic",
    referrer: str | None = None,
    cache_state: dict | None = None,
) -> dict[str, str]:
    """Generate HTTP headers with referrer and cache support.

    Args:
        user_agent: User-agent string.
        strategy: Header strategy.
        referrer: Referer URL to include.
        cache_state: Dict with 'etag' and/or 'last_modified' for conditional requests.

    Returns:
        Dict of HTTP headers.
    """
    # Build UA info dict for internal use
    ua_info: dict[str, str] | None = None
    if user_agent:
        browser = "chrome"
        for name in ("firefox", "edg", "chrome", "safari"):
            if name.lower() in user_agent.lower():
                browser = "edge" if name == "edg" else name
                break
        platform = "mobile" if "Mobile" in user_agent else "desktop"
        ua_info = {"ua": user_agent, "browser": browser, "platform": platform}

    headers = build_headers(ua_info, strategy)

    if referrer:
        headers["Referer"] = referrer

    if cache_state:
        headers = add_conditional_headers(
            headers,
            etag=cache_state.get("etag"),
            last_modified=cache_state.get("last_modified"),
        )

    return headers


def add_conditional_headers(
    headers: dict[str, str],
    etag: str | None = None,
    last_modified: str | None = None,
) -> dict[str, str]:
    """Add conditional request headers for cache validation."""
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    return headers


def build_headers(
    ua_info: dict[str, str] | None,
    strategy: str | None = "realistic",
    referrer: str | None = None,
) -> dict[str, str]:
    """Generate HTTP headers that match the given user agent.

    Args:
        ua_info: Dict from user_agent.pick_user_agent (ua, browser, platform).
        strategy: 'realistic' for full header set, 'minimal' for bare minimum,
                  or None to return empty dict.
        referrer: Optional Referer header value.

    Returns:
        Dict of HTTP headers.
    """
    if strategy is None:
        return {}

    headers: dict[str, str] = {}

    if ua_info:
        headers["User-Agent"] = ua_info["ua"]

    if strategy == "minimal":
        headers.setdefault("Accept", "*/*")
        return headers

    # Realistic headers
    browser = ua_info["browser"] if ua_info else "chrome"
    platform = ua_info["platform"] if ua_info else "desktop"

    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    headers["Accept-Language"] = "en-US,en;q=0.9"
    headers["Accept-Encoding"] = "gzip, deflate, br"
    headers["Cache-Control"] = "no-cache"
    headers["Pragma"] = "no-cache"

    if browser in ("chrome", "edge"):
        headers["Sec-Ch-Ua"] = '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'
        headers["Sec-Ch-Ua-Mobile"] = "?1" if platform == "mobile" else "?0"
        headers["Sec-Ch-Ua-Platform"] = _guess_platform(ua_info)
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        headers["Sec-Fetch-Site"] = "none"
        headers["Sec-Fetch-User"] = "?1"

    headers["Upgrade-Insecure-Requests"] = "1"

    if referrer:
        headers["Referer"] = referrer

    return headers


def build_image_headers(
    ua_info: dict[str, str] | None,
    referer: str | None = None,
    strategy: str | None = "realistic",
) -> dict[str, str]:
    """Generate headers suitable for image download requests.

    Args:
        ua_info: Dict from user_agent.pick_user_agent.
        referer: Referer URL to include.
        strategy: Header strategy.

    Returns:
        Dict of HTTP headers.
    """
    if strategy is None:
        return {}

    headers: dict[str, str] = {}

    if ua_info:
        headers["User-Agent"] = ua_info["ua"]

    if strategy == "minimal":
        headers["Accept"] = "image/*,*/*;q=0.8"
        if referer:
            headers["Referer"] = referer
        return headers

    headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    headers["Accept-Language"] = "en-US,en;q=0.9"
    headers["Accept-Encoding"] = "gzip, deflate, br"

    if referer:
        headers["Referer"] = referer

    browser = ua_info["browser"] if ua_info else "chrome"
    if browser in ("chrome", "edge"):
        headers["Sec-Fetch-Dest"] = "image"
        headers["Sec-Fetch-Mode"] = "no-cors"
        headers["Sec-Fetch-Site"] = "cross-site"

    return headers


def _guess_platform(ua_info: dict[str, str] | None) -> str:
    """Guess the Sec-Ch-Ua-Platform value from the UA string."""
    if not ua_info:
        return '"Windows"'
    ua = ua_info["ua"]
    if "Windows" in ua:
        return '"Windows"'
    if "Macintosh" in ua or "Mac OS" in ua:
        return '"macOS"'
    if "Linux" in ua and "Android" not in ua:
        return '"Linux"'
    if "Android" in ua:
        return '"Android"'
    if "iPhone" in ua or "iPad" in ua:
        return '"iOS"'
    return '"Windows"'
