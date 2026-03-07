"""Generate realistic browser headers matched to a given user-agent."""

from __future__ import annotations


def generate_headers(user_agent: str, strategy: str | None = "realistic") -> dict[str, str]:
    """Build a header dict that looks like a real browser request.

    When *strategy* is ``"realistic"`` (default), the headers are derived from
    the user-agent string so they are internally consistent.  Any other value
    returns a minimal set.
    """
    headers: dict[str, str] = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    if strategy != "realistic":
        return headers

    # Sec-Fetch-* headers (Chromium-based browsers)
    is_chrome = "Chrome/" in user_agent and "Edg/" not in user_agent
    is_edge = "Edg/" in user_agent
    is_firefox = "Firefox/" in user_agent

    if is_chrome or is_edge:
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        headers["Sec-Fetch-Site"] = "none"
        headers["Sec-Fetch-User"] = "?1"
        headers["Sec-Ch-Ua-Mobile"] = "?1" if "Mobile" in user_agent else "?0"

        if is_chrome:
            headers["Sec-Ch-Ua"] = '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'
            headers["Sec-Ch-Ua-Platform"] = _platform_from_ua(user_agent)
        elif is_edge:
            headers["Sec-Ch-Ua"] = '"Chromium";v="124", "Microsoft Edge";v="124", "Not-A.Brand";v="99"'
            headers["Sec-Ch-Ua-Platform"] = _platform_from_ua(user_agent)

    elif is_firefox:
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        headers["Sec-Fetch-Site"] = "none"
        headers["Sec-Fetch-User"] = "?1"

    return headers


def _platform_from_ua(ua: str) -> str:
    if "Windows" in ua:
        return '"Windows"'
    if "Macintosh" in ua:
        return '"macOS"'
    if "Android" in ua:
        return '"Android"'
    if "Linux" in ua:
        return '"Linux"'
    return '""'
