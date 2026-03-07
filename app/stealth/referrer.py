"""Referrer chain generation for plausible navigation paths."""

from __future__ import annotations

import random
from urllib.parse import urlparse


def pick_referrer(target_url: str) -> str:
    """Return a plausible referrer for the target URL.

    Distribution:
    - 60% Google search
    - 20% direct navigation (empty string)
    - 10% social media
    - 10% same domain
    """
    roll = random.random()

    if roll < 0.6:
        parsed = urlparse(target_url)
        domain = parsed.hostname or "example.com"
        keywords = domain.replace("www.", "").replace(".", " ").split()[0]
        return f"https://www.google.com/search?q={keywords}"

    if roll < 0.8:
        return ""

    if roll < 0.9:
        social = random.choice([
            "https://www.reddit.com/",
            "https://twitter.com/",
            "https://t.co/redirect",
            "https://www.facebook.com/",
        ])
        return social

    # Same domain
    parsed = urlparse(target_url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def build_referrer_chain(target_url: str, depth: int = 2) -> list[str]:
    """Build a sequence of URLs representing a navigation path.

    Args:
        target_url: Final destination URL.
        depth: Number of intermediate referrer hops.

    Returns:
        List of referrer URLs leading to the target.
    """
    chain: list[str] = []
    current = target_url
    for _ in range(depth):
        ref = pick_referrer(current)
        if ref:
            chain.insert(0, ref)
        current = ref or current
    return chain
