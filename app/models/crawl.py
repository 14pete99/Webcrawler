"""Crawl request / response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .stealth import StealthConfig


class ImageInfo(BaseModel):
    """Metadata for a single discovered image."""

    src: str
    alt: str = ""
    score: float = 0.0


class CrawlRequest(BaseModel):
    """Payload for POST /crawl and POST /crawl/extract."""

    url: str = Field(description="URL to crawl")
    screenshot: bool = Field(default=False, description="Capture a rendered screenshot")
    output_dir: str = Field(default="./output", description="Directory to save images")
    download_images: bool = Field(
        default=True,
        description="Download discovered images (False for extract-only)",
    )
    stealth: StealthConfig | None = Field(
        default=None,
        description="Inline stealth overrides (merged on top of profile)",
    )
    profile_id: str | None = Field(
        default="default",
        description="Stealth profile to load (null to skip)",
    )
    session_id: str | None = Field(
        default=None,
        description="Reuse a persistent browser/cookie session",
    )
    proxy: str | None = Field(default=None, description="Single proxy URL")
    proxy_file: str | None = Field(
        default=None,
        description="Path to file with one proxy URL per line",
    )


class CrawlResponse(BaseModel):
    """Response from POST /crawl and POST /crawl/extract."""

    success: bool
    url: str
    images_found: int = 0
    images_downloaded: int = 0
    manifest: list[dict] = Field(default_factory=list)
    screenshot_path: str | None = None
    errors: list[str] = Field(default_factory=list)
