"""Batch crawl orchestrator with concurrency, rate limiting, retry, and aggregation."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import time
import uuid
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from app.models.batch import (
    BatchCrawlRequest,
    BatchCrawlResponse,
    BatchJobStatus,
    URLResult,
)
from app.models.crawl import ImageInfo
from app.models.extraction import ExtractionConfig
from app.services.crawl4ai import crawl_url
from app.services.image_downloader import download_images
from app.stealth.pipeline import StealthContext

logger = logging.getLogger(__name__)

# Module-level job store for API progress tracking.
_jobs: dict[str, BatchJobStatus] = {}


def get_job(job_id: str) -> BatchJobStatus | None:
    return _jobs.get(job_id)


class BatchOrchestrator:
    """Orchestrates crawling multiple URLs with concurrency, rate limiting, and retry."""

    def __init__(
        self,
        *,
        urls: list[str],
        concurrency: int = 3,
        per_domain_delay: float = 2.0,
        max_retries: int = 2,
        output_dir: Path,
        download: bool = True,
        screenshot: bool = False,
        extraction: ExtractionConfig | None = None,
        stealth: StealthContext | None = None,
        proxy: str | None = None,
        cookies: list[dict] | None = None,
        api_base: str = "http://localhost:11235",
        timeout: float = 120,
        on_progress: object | None = None,
    ):
        self.urls = urls
        self.concurrency = concurrency
        self.per_domain_delay = per_domain_delay
        self.max_retries = max_retries
        self.output_dir = output_dir
        self.download = download
        self.screenshot = screenshot
        self.extraction = extraction
        self.stealth = stealth
        self.proxy = proxy
        self.cookies = cookies
        self.api_base = api_base
        self.timeout = timeout
        self.on_progress = on_progress

        self.job_id = str(uuid.uuid4())[:8]
        self._status = BatchJobStatus(
            job_id=self.job_id,
            status="running",
            total=len(urls),
        )
        _jobs[self.job_id] = self._status

    async def run(self) -> BatchCrawlResponse:
        """Execute the batch crawl and return aggregated results."""
        sem = asyncio.Semaphore(self.concurrency)
        domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        domain_last_request: dict[str, float] = {}
        results: list[URLResult] = [None] * len(self.urls)  # type: ignore[list-item]

        async def process_url(index: int, url: str) -> URLResult:
            domain = urlparse(url).netloc
            url_output_dir = self.output_dir / domain / f"{index:04d}"
            last_error = ""

            for attempt in range(1, self.max_retries + 2):
                async with sem:
                    # Per-domain rate limiting
                    async with domain_locks[domain]:
                        now = time.monotonic()
                        last = domain_last_request.get(domain, 0)
                        wait = last + self.per_domain_delay - now
                        if wait > 0:
                            await asyncio.sleep(wait)
                        domain_last_request[domain] = time.monotonic()

                    try:
                        data = await crawl_url(
                            url,
                            api_base=self.api_base,
                            screenshot=self.screenshot,
                            stealth=self.stealth,
                            proxy=self.proxy,
                            output_dir=url_output_dir,
                            timeout=self.timeout,
                            extraction=self.extraction,
                            cookies=self.cookies,
                        )
                    except Exception as exc:
                        last_error = str(exc)
                        if attempt <= self.max_retries:
                            backoff = min(2**attempt, 30)
                            logger.warning(
                                "[%d/%d] %s failed (attempt %d), retrying in %ds: %s",
                                index + 1, len(self.urls), url, attempt, backoff, last_error,
                            )
                            await asyncio.sleep(backoff)
                            continue
                        return URLResult(
                            url=url,
                            success=False,
                            attempt=attempt,
                            errors=[last_error],
                            output_dir=str(url_output_dir),
                        )

                    if not data.get("success"):
                        last_error = "; ".join(data.get("errors", ["unknown error"]))
                        if attempt <= self.max_retries:
                            backoff = min(2**attempt, 30)
                            logger.warning(
                                "[%d/%d] %s failed (attempt %d), retrying in %ds: %s",
                                index + 1, len(self.urls), url, attempt, backoff, last_error,
                            )
                            await asyncio.sleep(backoff)
                            continue
                        return URLResult(
                            url=url,
                            success=False,
                            attempt=attempt,
                            errors=[last_error],
                            output_dir=str(url_output_dir),
                        )

                    # Success — optionally download images
                    images_downloaded = 0
                    all_images: list[ImageInfo] = data.get("images", [])
                    if self.download and all_images:
                        url_output_dir.mkdir(parents=True, exist_ok=True)
                        dl_results = await download_images(
                            all_images,
                            url_output_dir,
                            stealth=self.stealth,
                            proxy=self.proxy,
                        )
                        images_downloaded = sum(1 for r in dl_results if r.success)

                    # Save per-URL extraction output
                    self._save_url_output(url_output_dir, data)

                    return URLResult(
                        url=url,
                        success=True,
                        attempt=attempt,
                        images_found=len(all_images),
                        images_downloaded=images_downloaded,
                        extracted_data=data.get("extracted_data"),
                        markdown=data.get("markdown"),
                        html=data.get("html"),
                        links=data.get("links"),
                        screenshot_path=data.get("screenshot_path"),
                        output_dir=str(url_output_dir),
                    )

            # Should not reach here, but safety net
            return URLResult(
                url=url, success=False, attempt=self.max_retries + 1,
                errors=[last_error or "max retries exceeded"],
            )

        # Launch all tasks
        tasks = [
            asyncio.create_task(process_url(i, url))
            for i, url in enumerate(self.urls)
        ]

        # Collect results as they complete, updating progress
        for coro in asyncio.as_completed(tasks):
            result = await coro
            idx = self.urls.index(result.url)
            results[idx] = result
            self._update_progress(result)

        # Aggregate
        combined_path = self._aggregate(results)

        # Finalize status
        self._status.status = "completed"
        self._status.results = results

        return BatchCrawlResponse(
            job_id=self.job_id,
            success=self._status.failed == 0,
            total=self._status.total,
            succeeded=self._status.succeeded,
            failed=self._status.failed,
            results=results,
            combined_output=str(combined_path) if combined_path else None,
            errors=self._status.errors,
        )

    def _update_progress(self, result: URLResult) -> None:
        self._status.completed += 1
        if result.success:
            self._status.succeeded += 1
        else:
            self._status.failed += 1
            self._status.errors.extend(result.errors)
        self._status.progress_pct = round(
            self._status.completed / self._status.total * 100, 1
        )
        if self.on_progress:
            self.on_progress(self._status)  # type: ignore[operator]

    def _save_url_output(self, url_output_dir: Path, data: dict) -> None:
        """Save per-URL extraction files (markdown, HTML, extracted data)."""
        url_output_dir.mkdir(parents=True, exist_ok=True)

        if data.get("markdown"):
            (url_output_dir / "page.md").write_text(
                data["markdown"], encoding="utf-8"
            )
        if data.get("html"):
            (url_output_dir / "page.html").write_text(
                data["html"], encoding="utf-8"
            )
        if data.get("extracted_data"):
            (url_output_dir / "extracted.json").write_text(
                json.dumps(data["extracted_data"], indent=2, default=str),
                encoding="utf-8",
            )
        if data.get("links"):
            (url_output_dir / "links.json").write_text(
                json.dumps(data["links"], indent=2, default=str),
                encoding="utf-8",
            )

    def _aggregate(self, results: list[URLResult]) -> Path | None:
        """Write combined output files to the base output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # combined.json — full results
        combined_path = self.output_dir / "combined.json"
        combined_data = [r.model_dump(exclude_none=True) for r in results]
        combined_path.write_text(
            json.dumps(combined_data, indent=2, default=str), encoding="utf-8"
        )

        # combined_extracted.json — merged extracted_data only
        all_extracted = []
        for r in results:
            if r.extracted_data is not None:
                if isinstance(r.extracted_data, list):
                    for item in r.extracted_data:
                        if isinstance(item, dict):
                            all_extracted.append({"_source_url": r.url, **item})
                        else:
                            all_extracted.append({"_source_url": r.url, "data": item})
                elif isinstance(r.extracted_data, dict):
                    all_extracted.append({"_source_url": r.url, **r.extracted_data})

        if all_extracted:
            (self.output_dir / "combined_extracted.json").write_text(
                json.dumps(all_extracted, indent=2, default=str), encoding="utf-8"
            )
            # Try CSV if data is tabular (flat dicts with consistent keys)
            self._try_write_csv(all_extracted)

        return combined_path

    def _try_write_csv(self, records: list[dict]) -> None:
        """Write combined.csv if records are flat dicts with consistent keys."""
        if not records:
            return

        # Check if all records have the same top-level keys and no nested values
        all_keys: set[str] = set()
        for rec in records:
            for k, v in rec.items():
                if isinstance(v, (dict, list)):
                    return  # Not flat — skip CSV
                all_keys.add(k)

        fieldnames = sorted(all_keys)
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)

        # Write with newline="" to prevent double \r\n on Windows
        csv_path = self.output_dir / "combined.csv"
        csv_path.write_bytes(buf.getvalue().encode("utf-8"))
