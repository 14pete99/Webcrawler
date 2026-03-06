"""User-agent pool and generator."""

from __future__ import annotations

import random

# Curated pool of recent, common user agents (Chrome/Firefox/Edge, desktop/mobile)
_UA_POOL: list[dict[str, str]] = [
    # Chrome desktop
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "browser": "chrome",
        "platform": "desktop",
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "browser": "chrome",
        "platform": "desktop",
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "browser": "chrome",
        "platform": "desktop",
    },
    # Firefox desktop
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "browser": "firefox",
        "platform": "desktop",
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
        "browser": "firefox",
        "platform": "desktop",
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "browser": "firefox",
        "platform": "desktop",
    },
    # Edge desktop
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "browser": "edge",
        "platform": "desktop",
    },
    # Chrome mobile
    {
        "ua": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
        "browser": "chrome",
        "platform": "mobile",
    },
    {
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/124.0.6367.88 Mobile/15E148 Safari/604.1",
        "browser": "chrome",
        "platform": "mobile",
    },
    # Safari mobile
    {
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
        "browser": "safari",
        "platform": "mobile",
    },
]


def pick_user_agent(choice: str | None = "random") -> dict[str, str] | None:
    """Pick a user agent from the pool.

    Args:
        choice: 'random' to pick randomly, a specific UA string to wrap it,
                or None to skip UA selection.

    Returns:
        Dict with 'ua', 'browser', 'platform' keys, or None if skipped.
    """
    if choice is None:
        return None
    if choice == "random":
        return random.choice(_UA_POOL)
    # Treat as a literal UA string — guess browser from content
    browser = "unknown"
    for name in ("firefox", "edg", "chrome", "safari"):
        if name.lower() in choice.lower():
            browser = "edge" if name == "edg" else name
            break
    platform = "mobile" if "Mobile" in choice else "desktop"
    return {"ua": choice, "browser": browser, "platform": platform}
