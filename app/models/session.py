"""Session info models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    """Metadata about a persistent session."""

    id: str = Field(description="Session identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: datetime = Field(default_factory=datetime.utcnow)
    has_cookies: bool = Field(default=False, description="Whether cookie jar has entries")
    cookie_count: int = Field(default=0, description="Number of cookies stored")
    has_browser_session: bool = Field(
        default=False,
        description="Whether a crawl4ai browser session exists",
    )
    has_local_storage: bool = Field(default=False, description="Whether localStorage data is stored")
    fingerprint_seed: int | None = Field(default=None, description="Fingerprint seed for session consistency")
