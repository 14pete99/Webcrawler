"""Common viewport dimension pool."""

from __future__ import annotations

import random

_VIEWPORT_POOL: list[tuple[int, int]] = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1280, 720),
    (1600, 900),
    (2560, 1440),
    (1280, 800),
    # Mobile
    (412, 915),
    (390, 844),
]


def pick_viewport(setting: str | None = "random") -> tuple[int, int]:
    """Return a ``(width, height)`` tuple.

    *setting* can be ``"random"``/``None`` for a random pick, or
    ``"WIDTHxHEIGHT"`` (e.g. ``"1920x1080"``).
    """
    if setting is None or setting == "random":
        return random.choice(_VIEWPORT_POOL)
    parts = setting.lower().split("x")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return random.choice(_VIEWPORT_POOL)
