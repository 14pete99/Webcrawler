"""Pydantic models for the webcrawler API."""

from .crawl import CrawlRequest, CrawlResponse, ImageInfo
from .download import DownloadRequest, DownloadResponse, DownloadResult
from .session import SessionInfo
from .batch import BatchCrawlRequest, BatchCrawlResponse, BatchJobStatus, URLResult
from .stealth import StealthConfig, StealthProfile

__all__ = [
    "BatchCrawlRequest",
    "BatchCrawlResponse",
    "BatchJobStatus",
    "CrawlRequest",
    "CrawlResponse",
    "DownloadRequest",
    "DownloadResponse",
    "DownloadResult",
    "ImageInfo",
    "SessionInfo",
    "StealthConfig",
    "StealthProfile",
    "URLResult",
]
