"""Stealth pipeline — composes all stealth modules into a single context."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.stealth import StealthConfig

from .delays import make_delay_func
from .headers import build_headers, build_image_headers
from .javascript import build_js_injection, get_js_scripts
from .tls import pick_tls_profile
from .user_agent import pick_user_agent
from .viewport import pick_viewport


@dataclass
class StealthContext:
    """Assembled stealth context consumed by crawl4ai and image_downloader."""

    user_agent_info: dict[str, str] | None = None
    page_headers: dict[str, str] = field(default_factory=dict)
    image_headers: dict[str, str] = field(default_factory=dict)
    js_injection: str | None = None
    js_scripts: list[str] = field(default_factory=list)
    viewport: tuple[int, int] | None = None
    delay_func: Callable[[], float] | None = None
    tls_profile: object | None = None
    behavior_scripts: list[str] = field(default_factory=list)
    geo_profile: object | None = None


def build_stealth_context(
    config: StealthConfig | None = None,
    target_url: str | None = None,
    proxy_country: str | None = None,
) -> StealthContext:
    """Build a StealthContext by running all stealth modules in order.

    Args:
        config: Stealth configuration (from profile, inline, or merged).
        target_url: Target URL for referrer generation.
        proxy_country: Proxy country code for geo consistency.

    Returns:
        A fully populated StealthContext.
    """
    if config is None:
        config = StealthConfig()

    # 1. User agent
    ua_info = pick_user_agent(config.user_agent)

    # 2. Headers (with optional referrer)
    referrer = None
    if config.referrer_chain and target_url:
        from .referrer import pick_referrer

        referrer = pick_referrer(target_url)

    page_headers = build_headers(ua_info, config.headers, referrer=referrer)
    img_headers = build_image_headers(ua_info, strategy=config.headers)

    # 3. JS injection (with fingerprint hardening)
    fingerprint_config = {
        "canvas_spoof": config.canvas_spoof,
        "webgl_spoof": config.webgl_spoof,
        "audio_spoof": config.audio_spoof,
        "hardware_spoof": config.hardware_spoof,
        "font_mask": config.font_mask,
        "fingerprint_seed": config.fingerprint_seed,
    }
    js_scripts = get_js_scripts(config.js_injection, fingerprint_config=fingerprint_config)

    # Storage seeding (pre-load)
    if config.storage_seed:
        from .cookies import seed_storage_js

        js_scripts.insert(0, seed_storage_js(config.storage_seed))

    js = "\n".join(js_scripts) if js_scripts else None

    # 4. Viewport
    vp = pick_viewport(config.viewport)

    # 5. Delays (with distribution)
    delay_fn = make_delay_func(
        config.delay_min_ms,
        config.delay_max_ms,
        distribution=config.delay_distribution,
    )

    # 6. TLS profile
    ua_string = ua_info["ua"] if ua_info else "Mozilla/5.0 Chrome/124"
    tls_profile = pick_tls_profile(ua_string)

    # 7. Behavioral simulation (post-load scripts)
    from .behavior import build_behavior_script

    behavior_vp = vp if vp else (1920, 1080)
    behavior_scripts = build_behavior_script(config, behavior_vp)

    # Cookie consent dismissal (post-load)
    if config.cookie_consent_dismiss:
        from .cookies import cookie_consent_js

        behavior_scripts.append(cookie_consent_js())

    # 8. Geo consistency — match timezone/locale to proxy country
    geo_profile = None
    if config.geo_consistency and proxy_country:
        from .geo import geo_override_js, match_geo_to_proxy

        from app.services.proxy import ProxyEntry

        dummy_entry = ProxyEntry(url="", country=proxy_country)
        geo_profile = match_geo_to_proxy(dummy_entry)
        if geo_profile:
            js_scripts.append(geo_override_js(geo_profile))
            js = "\n".join(js_scripts) if js_scripts else None

    return StealthContext(
        user_agent_info=ua_info,
        page_headers=page_headers,
        image_headers=img_headers,
        js_injection=js,
        js_scripts=js_scripts,
        viewport=vp,
        delay_func=delay_fn,
        tls_profile=tls_profile,
        behavior_scripts=behavior_scripts,
        geo_profile=geo_profile,
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
