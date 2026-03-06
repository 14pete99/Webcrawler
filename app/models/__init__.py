"""Pydantic models for the webcrawler API."""

from .crawl import CrawlRequest, CrawlResponse, ImageInfo
from .download import DownloadRequest, DownloadResponse, DownloadResult
from .session import SessionInfo
from .stealth import StealthConfig, StealthProfile

__all__ = [
    "CrawlRequest",
    "CrawlResponse",
    "DownloadRequest",
    "DownloadResponse",
    "DownloadResult",
    "ImageInfo",
    "SessionInfo",
    "StealthConfig",
    "StealthProfile",
]
