from __future__ import annotations

from pydantic import BaseModel


class SessionInfo(BaseModel):
    """Metadata about a persisted session."""

    id: str
    has_cookies: bool = False
    cookie_count: int = 0
