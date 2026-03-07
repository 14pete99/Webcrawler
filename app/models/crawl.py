from __future__ import annotations

from pydantic import BaseModel, Field

from .stealth import StealthConfig


class CrawlRequest(BaseModel):
    """Request body for POST /crawl and POST /crawl/extract."""

    url: str
    screenshot: bool = False
    output_dir: str = "./output"
    download_images: bool = True
    stealth: StealthConfig | None = None
    profile_id: str | None = Field(
        default=None,
        description="Load stealth settings from a saved profile",
    )
    session_id: str | None = None
    proxy: str | None = None
    proxy_file: str | None = None


class ImageInfo(BaseModel):
    src: str
    alt: str = ""
    score: float = 0.0


class CrawlResponse(BaseModel):
    success: bool
    url: str
    images_found: int = 0
    images_downloaded: int = 0
    manifest: list[dict] = Field(default_factory=list)
    screenshot_path: str | None = None
    errors: list[str] = Field(default_factory=list)
