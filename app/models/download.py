"""Download request / response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .crawl import ImageInfo
from .stealth import StealthConfig


class DownloadRequest(BaseModel):
    """Payload for POST /download."""

    images: list[ImageInfo] = Field(description="List of image URLs to download")
    output_dir: str = Field(default="./output", description="Directory to save images")
    stealth: StealthConfig | None = Field(
        default=None,
        description="Inline stealth overrides",
    )
    profile_id: str | None = Field(
        default=None,
        description="Stealth profile to load",
    )
    session_id: str | None = Field(
        default=None,
        description="Reuse a persistent cookie session",
    )
    proxy: str | None = Field(default=None, description="Single proxy URL")


class DownloadResult(BaseModel):
    """Result for a single image download."""

    src: str
    file: str | None = None
    alt: str = ""
    error: str | None = None
    extra_files: list[str] | None = None


class DownloadResponse(BaseModel):
    """Response from POST /download."""

    success: bool
    total: int = 0
    downloaded: int = 0
    results: list[DownloadResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
