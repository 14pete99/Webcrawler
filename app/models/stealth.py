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


class StealthProfile(BaseModel):
    """A named, persisted stealth configuration."""

    id: str = Field(description="Unique profile identifier")
    name: str = Field(default="", description="Human-readable profile name")
    config: StealthConfig = Field(default_factory=StealthConfig)
