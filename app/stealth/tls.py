"""TLS profile pool matched to user-agents."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TLSProfile:
    """TLS fingerprint profile matched to a browser version."""

    browser: str          # e.g. "chrome_124", "firefox_125"
    ja3_hash: str         # for reference/logging
    impersonate: str      # curl_cffi impersonate string


_TLS_PROFILES: list[TLSProfile] = [
    TLSProfile(
        browser="chrome_124",
        ja3_hash="773906b0efdefa24a7f2b8eb6985bf37",
        impersonate="chrome124",
    ),
    TLSProfile(
        browser="chrome_123",
        ja3_hash="cd08e31494816f6e8d29f3c9ba80a92c",
        impersonate="chrome123",
    ),
    TLSProfile(
        browser="chrome_120",
        ja3_hash="c45bfe41eca0e4004a262ad4a245a057",
        impersonate="chrome120",
    ),
    TLSProfile(
        browser="firefox_125",
        ja3_hash="579ccef312d18482fc42e2b822ca2430",
        impersonate="firefox125",
    ),
    TLSProfile(
        browser="firefox_120",
        ja3_hash="a]b7c9d8e1f2a3b4c5d6e7f8a9b0c1d2",
        impersonate="firefox120",
    ),
    TLSProfile(
        browser="edge_124",
        ja3_hash="d9a5bb8aa2cf6e3d4b7e5a1c9f2d4e6a",
        impersonate="edge124",
    ),
    TLSProfile(
        browser="safari_17",
        ja3_hash="e4e36c28b72a2b4e1f5c7d8a9b0e1f2c",
        impersonate="safari17_0",
    ),
]

# Map browser family to preferred profiles (ordered by preference)
_BROWSER_MAP: dict[str, list[str]] = {
    "chrome": ["chrome_124", "chrome_123", "chrome_120"],
    "firefox": ["firefox_125", "firefox_120"],
    "edge": ["edge_124", "chrome_124"],
    "safari": ["safari_17"],
}

_PROFILES_BY_BROWSER = {p.browser: p for p in _TLS_PROFILES}


def pick_tls_profile(user_agent: str) -> TLSProfile:
    """Pick a TLS profile matching the given user-agent string.

    Parses the UA to identify browser family and version, then picks the
    closest matching TLS profile. Falls back to Chrome if no match.
    """
    ua_lower = user_agent.lower()

    # Detect browser family
    family = "chrome"  # default
    if "firefox/" in ua_lower:
        family = "firefox"
    elif "edg/" in ua_lower:
        family = "edge"
    elif "safari/" in ua_lower and "chrome" not in ua_lower:
        family = "safari"

    # Try to match version
    version_match = None
    if family == "firefox":
        m = re.search(r"firefox/(\d+)", ua_lower)
        if m:
            version_match = int(m.group(1))
    elif family == "edge":
        m = re.search(r"edg/(\d+)", ua_lower)
        if m:
            version_match = int(m.group(1))
    elif family == "safari":
        m = re.search(r"version/(\d+)", ua_lower)
        if m:
            version_match = int(m.group(1))
    else:
        m = re.search(r"chrome/(\d+)", ua_lower)
        if m:
            version_match = int(m.group(1))

    # Find closest profile
    candidates = _BROWSER_MAP.get(family, _BROWSER_MAP["chrome"])
    if version_match is not None:
        target = f"{family}_{version_match}"
        if target in _PROFILES_BY_BROWSER:
            return _PROFILES_BY_BROWSER[target]

    # Return first candidate that exists
    for name in candidates:
        if name in _PROFILES_BY_BROWSER:
            return _PROFILES_BY_BROWSER[name]

    return _TLS_PROFILES[0]
