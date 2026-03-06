"""Viewport dimension pool."""

from __future__ import annotations

import random

# Common screen resolutions: (width, height)
_VIEWPORT_POOL: dict[str, tuple[int, int]] = {
    "1920x1080": (1920, 1080),
    "1366x768": (1366, 768),
    "1536x864": (1536, 864),
    "1440x900": (1440, 900),
    "1280x720": (1280, 720),
    "2560x1440": (2560, 1440),
    "1600x900": (1600, 900),
    "1280x1024": (1280, 1024),
    # Mobile
    "390x844": (390, 844),
    "414x896": (414, 896),
    "360x800": (360, 800),
}


def pick_viewport(choice: str | None = "random") -> tuple[int, int] | None:
    """Pick a viewport from the pool.

    Args:
        choice: 'random' to pick randomly, a preset name (e.g. '1920x1080'),
                or None to skip viewport selection.

    Returns:
        (width, height) tuple, or None if skipped.
    """
    if choice is None:
        return None
    if choice == "random":
        return random.choice(list(_VIEWPORT_POOL.values()))
    if choice in _VIEWPORT_POOL:
        return _VIEWPORT_POOL[choice]
    # Try parsing "WxH" format
    try:
        w, h = choice.lower().split("x")
        return (int(w), int(h))
    except (ValueError, AttributeError):
        return random.choice(list(_VIEWPORT_POOL.values()))
