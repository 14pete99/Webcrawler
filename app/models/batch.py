"""Batch crawl request / response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .extraction import ExtractionConfig
from .stealth import StealthConfig


class URLResult(BaseModel):
    """Result for a single URL within a batch."""

    url: str
    success: bool
    attempt: int = Field(default=1, description="Which attempt succeeded (or last attempt)")
    images_found: int = 0
    images_downloaded: int = 0
    extracted_data: list[dict] | dict | None = None
    markdown: str | None = None
    html: str | None = None
    links: list[dict] | None = None
    screenshot_path: str | None = None
    errors: list[str] = Field(default_factory=list)
    output_dir: str | None = None


class BatchCrawlRequest(BaseModel):
    """Payload for POST /batch/crawl."""

    urls: list[str] = Field(min_length=1, description="URLs to crawl")
    concurrency: int = Field(default=3, ge=1, le=20, description="Max parallel crawls")
    per_domain_delay: float = Field(
        default=2.0, ge=0, description="Seconds between requests to same domain"
    )
    max_retries: int = Field(default=2, ge=0, le=5, description="Max retry attempts per URL")
    output_dir: str = Field(default="./output", description="Base output directory")
    download_images: bool = Field(default=True, description="Download discovered images")
    screenshot: bool = Field(default=False, description="Capture screenshot per URL")
    extraction: ExtractionConfig | None = Field(
        default=None, description="Shared extraction config for all URLs"
    )
    stealth: StealthConfig | None = Field(
        default=None, description="Inline stealth overrides"
    )
    profile_id: str | None = Field(default="default", description="Stealth profile to load")
    proxy: str | None = Field(default=None, description="Single proxy URL")
    proxy_file: str | None = Field(default=None, description="Proxy file path")
    cookies_file: str | None = Field(
        default=None, description="Path to shared cookie file (JSON or Netscape)"
    )


class BatchJobStatus(BaseModel):
    """Status of a running or completed batch job."""

    job_id: str
    status: Literal["running", "completed", "failed"] = "running"
    total: int = 0
    completed: int = 0
    succeeded: int = 0
    failed: int = 0
    progress_pct: float = 0.0
    results: list[URLResult] | None = None
    errors: list[str] = Field(default_factory=list)


class BatchCrawlResponse(BaseModel):
    """Final response for a completed batch."""

    job_id: str
    success: bool
    total: int
    succeeded: int
    failed: int
    results: list[URLResult]
    combined_output: str | None = Field(
        default=None, description="Path to combined.json"
    )
    errors: list[str] = Field(default_factory=list)
