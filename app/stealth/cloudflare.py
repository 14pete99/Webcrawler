"""Cloudflare challenge detection and bypass configuration."""

from __future__ import annotations

import re

_CF_MARKERS = [
    "cf-browser-verification",
    "__cf_chl_",
    "challenges.cloudflare.com",
    "cf_chl_opt",
]

_CF_TITLE = re.compile(r"<title>\s*Just a moment\.\.\.\s*</title>", re.IGNORECASE)


def detect_cloudflare_challenge(html: str) -> bool:
    """Check if the HTML contains Cloudflare challenge markers."""
    if _CF_TITLE.search(html):
        return True
    for marker in _CF_MARKERS:
        if marker in html:
            return True
    return False


def detect_challenge_type(html: str) -> str | None:
    """Identify the type of Cloudflare challenge.

    Returns:
        "js_challenge", "turnstile", "managed", or None if not a CF challenge.
    """
    if not detect_cloudflare_challenge(html):
        return None

    if "challenges.cloudflare.com/turnstile" in html or "cf-turnstile" in html:
        return "turnstile"

    if "managed_checking_msg" in html or "cf-im-under-attack" in html:
        return "managed"

    return "js_challenge"


def build_cf_bypass_config(challenge_type: str) -> dict:
    """Return crawl4ai CrawlerRunConfig params optimized for the challenge.

    Args:
        challenge_type: One of "js_challenge", "turnstile", "managed".

    Returns:
        Dict of CrawlerRunConfig params to pass to crawl4ai.
    """
    base = {
        "page_timeout": 60000,
        "delay_before_return_html": 5.0,
    }

    if challenge_type == "js_challenge":
        base["wait_for"] = "css:body:not(.no-js)"
        base["page_timeout"] = 30000
    elif challenge_type == "turnstile":
        base["wait_for"] = "css:input[name='cf-turnstile-response']"
        base["page_timeout"] = 60000
        base["delay_before_return_html"] = 8.0
    elif challenge_type == "managed":
        base["page_timeout"] = 45000
        base["delay_before_return_html"] = 10.0

    return base


def turnstile_callback_js(token: str) -> str:
    """JS that injects a solved Turnstile token into the page's callback."""
    token_escaped = token.replace("\\", "\\\\").replace("'", "\\'")
    return f"""
(function() {{
    var input = document.querySelector('input[name="cf-turnstile-response"]');
    if (input) {{
        input.value = '{token_escaped}';
        var event = new Event('input', {{ bubbles: true }});
        input.dispatchEvent(event);
    }}
    // Try to invoke the callback directly
    if (typeof window.turnstileCallback === 'function') {{
        window.turnstileCallback('{token_escaped}');
    }}
    // Also try common callback names
    if (typeof window.__cf_chl_done === 'function') {{
        window.__cf_chl_done('{token_escaped}');
    }}
}})();
"""
