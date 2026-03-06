from __future__ import annotations

from pydantic import BaseModel, Field


class StealthConfig(BaseModel):
    """Inline stealth configuration provided per-request."""

    user_agent: str | None = Field(
        default="random",
        description="User-agent string or 'random' to pick from the pool",
    )
    headers: str | None = Field(
        default="realistic",
        description="Header strategy: 'realistic' generates browser-matched headers",
    )
    js_injection: bool = Field(
        default=True,
        description="Inject JS patches (navigator.webdriver, etc.)",
    )
    viewport: str | None = Field(
        default="random",
        description="Viewport preset or 'random'",
    )
    delay_min_ms: int = Field(default=1000, ge=0)
    delay_max_ms: int = Field(default=3000, ge=0)


class StealthProfile(BaseModel):
    """A named, persisted stealth configuration."""

    id: str = Field(..., description="Unique profile identifier")
    name: str = Field(default="", description="Human-friendly name")
    config: StealthConfig = Field(default_factory=StealthConfig)
