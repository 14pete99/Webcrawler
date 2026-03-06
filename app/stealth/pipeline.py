"""Compose all stealth modules into a single context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..models.stealth import StealthConfig
from .delays import make_delay_fn
from .headers import generate_headers
from .javascript import get_js_scripts
from .user_agent import pick_user_agent
from .viewport import pick_viewport


@dataclass
class StealthContext:
    """Aggregated stealth state consumed by services."""

    user_agent: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    js_scripts: list[str] = field(default_factory=list)
    viewport: tuple[int, int] = (1920, 1080)
    delay_fn: Callable[[], float] = field(default_factory=lambda: make_delay_fn())


def build_stealth_context(config: StealthConfig | None = None) -> StealthContext:
    """Run the stealth pipeline and return a populated :class:`StealthContext`.

    1. Pick user-agent
    2. Generate matching headers
    3. Collect JS injection scripts
    4. Pick viewport dimensions
    5. Create delay callable
    """
    if config is None:
        config = StealthConfig()

    ua = pick_user_agent(config.user_agent)
    headers = generate_headers(ua, config.headers)
    js_scripts = get_js_scripts(config.js_injection)
    viewport = pick_viewport(config.viewport)
    delay_fn = make_delay_fn(config.delay_min_ms, config.delay_max_ms)

    return StealthContext(
        user_agent=ua,
        headers=headers,
        js_scripts=js_scripts,
        viewport=viewport,
        delay_fn=delay_fn,
    )
