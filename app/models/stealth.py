"""Stealth configuration and profile models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StealthConfig(BaseModel):
    """Inline stealth settings provided per-request."""

    user_agent: str | None = Field(
        default="random",
        description="Specific UA string, 'random' to pick from pool, or null to skip",
    )
    headers: Literal["realistic", "minimal"] | None = Field(
        default="realistic",
        description="Header generation strategy",
    )
    js_injection: bool = Field(
        default=True,
        description="Inject anti-detection JS (navigator.webdriver patch, etc.)",
    )
    viewport: str | None = Field(
        default="random",
        description="Viewport preset name, 'random', or null to use browser default",
    )
    delay_min_ms: int = Field(
        default=1000,
        ge=0,
        description="Minimum random delay between requests (ms)",
    )
    delay_max_ms: int = Field(
        default=3000,
        ge=0,
        description="Maximum random delay between requests (ms)",
    )

    # Task 02: Browser fingerprint hardening
    canvas_spoof: bool = Field(default=True, description="Spoof canvas fingerprint")
    webgl_spoof: bool = Field(default=True, description="Spoof WebGL fingerprint")
    audio_spoof: bool = Field(default=True, description="Spoof AudioContext fingerprint")
    hardware_spoof: bool = Field(default=True, description="Spoof hardwareConcurrency/deviceMemory")
    font_mask: bool = Field(default=True, description="Mask font enumeration")
    fingerprint_seed: int | None = Field(default=None, description="Seed for fingerprint noise; None = random per session")

    # Task 04: Behavioral simulation
    mouse_simulation: bool = Field(default=False, description="Simulate mouse movements post-load")
    scroll_simulation: bool = Field(default=False, description="Simulate scroll patterns post-load")
    keyboard_simulation: bool = Field(default=False, description="Simulate keyboard input timing")
    dwell_time: bool = Field(default=False, description="Add random page dwell time")

    # Task 05: Session & request sophistication
    cookie_consent_dismiss: bool = Field(default=False, description="Auto-dismiss cookie consent banners")
    referrer_chain: bool = Field(default=False, description="Generate plausible Referer headers")
    delay_distribution: str = Field(default="uniform", description="Delay distribution: uniform|gaussian|poisson|lognormal")
    asset_simulation: bool = Field(default=False, description="Fetch CSS/JS assets to simulate browser loading")
    storage_seed: dict[str, str] | None = Field(default=None, description="Key-value pairs to seed in localStorage")

    # Task 06: Infrastructure
    captcha_solving: bool = Field(default=False, description="Enable CAPTCHA solving via external API")
    cloudflare_bypass: bool = Field(default=False, description="Detect and attempt to bypass Cloudflare challenges")
    geo_consistency: bool = Field(default=True, description="Auto-match timezone/locale to proxy country")


class StealthProfile(BaseModel):
    """A named, persisted stealth configuration."""

    id: str = Field(description="Unique profile identifier")
    name: str = Field(default="", description="Human-readable profile name")
    config: StealthConfig = Field(default_factory=StealthConfig)
