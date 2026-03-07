"""Stealth pipeline — composes all stealth modules into a single context."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.stealth import StealthConfig

from .delays import make_delay_func
from .headers import build_headers, build_image_headers
from .javascript import build_js_injection
from .user_agent import pick_user_agent
from .viewport import pick_viewport


@dataclass
class StealthContext:
    """Assembled stealth context consumed by crawl4ai and image_downloader."""

    user_agent_info: dict[str, str] | None = None
    page_headers: dict[str, str] = field(default_factory=dict)
    image_headers: dict[str, str] = field(default_factory=dict)
    js_injection: str | None = None
    viewport: tuple[int, int] | None = None
    delay_func: Callable[[], float] | None = None


def build_stealth_context(config: StealthConfig) -> StealthContext:
    """Build a StealthContext by running all stealth modules in order.

    Args:
        config: Stealth configuration (from profile, inline, or merged).

    Returns:
        A fully populated StealthContext.
    """
    # 1. User agent
    ua_info = pick_user_agent(config.user_agent)

    # 2. Headers
    page_headers = build_headers(ua_info, config.headers)
    img_headers = build_image_headers(ua_info, strategy=config.headers)

    # 3. JS injection
    js = build_js_injection(config.js_injection)

    # 4. Viewport
    vp = pick_viewport(config.viewport)

    # 5. Delays
    delay_fn = make_delay_func(config.delay_min_ms, config.delay_max_ms)

    return StealthContext(
        user_agent_info=ua_info,
        page_headers=page_headers,
        image_headers=img_headers,
        js_injection=js,
        viewport=vp,
        delay_func=delay_fn,
    )


def merge_stealth_configs(
    base: StealthConfig | None,
    override: StealthConfig | None,
) -> StealthConfig:
    """Merge two stealth configs. Override values take precedence over base.

    Args:
        base: Base config (e.g. from a saved profile).
        override: Inline overrides from the request.

    Returns:
        Merged StealthConfig.
    """
    if base is None and override is None:
        return StealthConfig()
    if base is None:
        return override  # type: ignore[return-value]
    if override is None:
        return base

    base_dict = base.model_dump()
    override_dict = override.model_dump(exclude_unset=True)
    base_dict.update(override_dict)
    return StealthConfig(**base_dict)
