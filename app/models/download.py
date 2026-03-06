from __future__ import annotations

from pydantic import BaseModel, Field

from .crawl import ImageInfo
from .stealth import StealthConfig


class DownloadRequest(BaseModel):
    """Request body for POST /download."""

    images: list[ImageInfo]
    output_dir: str = "./output"
    stealth: StealthConfig | None = None
    profile_id: str | None = None
    session_id: str | None = None
    proxy: str | None = None


class DownloadResponse(BaseModel):
    success: bool
    downloaded: int = 0
    failed: int = 0
    manifest: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
