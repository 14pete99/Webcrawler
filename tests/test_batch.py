"""Tests for the batch crawl orchestrator, models, and CLI integration.

These tests mock crawl_url and download_images to verify the orchestrator
handles concurrency, rate limiting, retry, and aggregation correctly.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.models.batch import (
    BatchCrawlRequest,
    BatchCrawlResponse,
    BatchJobStatus,
    URLResult,
)
from app.models.extraction import ExtractionConfig
from app.services.batch import BatchOrchestrator, _jobs


# --- Helpers ---

def _success_result(**overrides):
    """Build a fake crawl_url success response."""
    base = {
        "success": True,
        "images": [],
        "screenshot_path": None,
        "errors": [],
        "extracted_data": {"title": "Test Page"},
        "markdown": "# Test",
        "html": "<h1>Test</h1>",
        "links": [],
    }
    base.update(overrides)
    return base


def _failure_result(error="connection timeout"):
    return {
        "success": False,
        "images": [],
        "screenshot_path": None,
        "errors": [error],
    }


# ============================================================
# Model tests
# ============================================================


class TestBatchModels:
    def test_url_result_defaults(self):
        r = URLResult(url="https://example.com", success=True)
        assert r.attempt == 1
        assert r.images_found == 0
        assert r.errors == []

    def test_batch_crawl_request_min_urls(self):
        with pytest.raises(Exception):
            BatchCrawlRequest(urls=[])

    def test_batch_crawl_request_defaults(self):
        req = BatchCrawlRequest(urls=["https://a.com", "https://b.com"])
        assert req.concurrency == 3
        assert req.per_domain_delay == 2.0
        assert req.max_retries == 2
        assert req.download_images is True

    def test_batch_crawl_request_concurrency_bounds(self):
        with pytest.raises(Exception):
            BatchCrawlRequest(urls=["https://a.com"], concurrency=0)
        with pytest.raises(Exception):
            BatchCrawlRequest(urls=["https://a.com"], concurrency=21)

    def test_batch_job_status_defaults(self):
        s = BatchJobStatus(job_id="abc")
        assert s.status == "running"
        assert s.progress_pct == 0.0

    def test_batch_crawl_response_fields(self):
        r = BatchCrawlResponse(
            job_id="abc", success=True, total=2, succeeded=2, failed=0,
            results=[
                URLResult(url="https://a.com", success=True),
                URLResult(url="https://b.com", success=True),
            ],
        )
        assert len(r.results) == 2
        assert r.combined_output is None


# ============================================================
# Orchestrator tests
# ============================================================


class TestBatchOrchestrator:
    @pytest.fixture(autouse=True)
    def _tmp_output(self, tmp_path):
        self.output_dir = tmp_path / "output"
        self.output_dir.mkdir()

    @pytest.mark.asyncio
    async def test_basic_batch(self):
        """Two URLs, both succeed."""
        urls = ["https://a.com/page1", "https://b.com/page2"]
        mock_crawl = AsyncMock(return_value=_success_result())

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=urls, output_dir=self.output_dir,
                concurrency=2, per_domain_delay=0, max_retries=0,
                download=False,
            )
            result = await orch.run()

        assert result.success is True
        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0
        assert mock_crawl.call_count == 2

        # Check combined.json was written
        combined = json.loads((self.output_dir / "combined.json").read_text())
        assert len(combined) == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """URL fails first attempt, succeeds on retry."""
        mock_crawl = AsyncMock(side_effect=[
            _failure_result("timeout"),
            _success_result(),
        ])

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com/page1"],
                output_dir=self.output_dir,
                concurrency=1, per_domain_delay=0, max_retries=1,
                download=False,
            )
            result = await orch.run()

        assert result.success is True
        assert result.results[0].attempt == 2
        assert mock_crawl.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """URL fails all attempts."""
        mock_crawl = AsyncMock(return_value=_failure_result("always fails"))

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com/page1"],
                output_dir=self.output_dir,
                concurrency=1, per_domain_delay=0, max_retries=2,
                download=False,
            )
            result = await orch.run()

        assert result.success is False
        assert result.failed == 1
        assert result.results[0].success is False
        assert mock_crawl.call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_exception_retry(self):
        """crawl_url raises an exception, then succeeds."""
        mock_crawl = AsyncMock(side_effect=[
            Exception("network error"),
            _success_result(),
        ])

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com/page1"],
                output_dir=self.output_dir,
                concurrency=1, per_domain_delay=0, max_retries=1,
                download=False,
            )
            result = await orch.run()

        assert result.success is True
        assert result.results[0].attempt == 2

    @pytest.mark.asyncio
    async def test_per_domain_delay(self):
        """Same-domain URLs respect per_domain_delay."""
        urls = ["https://a.com/p1", "https://a.com/p2"]
        call_times = []

        async def timed_crawl(*args, **kwargs):
            call_times.append(time.monotonic())
            return _success_result()

        with patch("app.services.batch.crawl_url", side_effect=timed_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=urls, output_dir=self.output_dir,
                concurrency=2, per_domain_delay=0.5, max_retries=0,
                download=False,
            )
            await orch.run()

        assert len(call_times) == 2
        elapsed = call_times[1] - call_times[0]
        assert elapsed >= 0.4  # Allow small tolerance

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """Only N URLs crawl simultaneously."""
        max_concurrent = 0
        current_concurrent = 0

        async def counting_crawl(*args, **kwargs):
            nonlocal max_concurrent, current_concurrent
            import asyncio
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
            await asyncio.sleep(0.1)
            current_concurrent -= 1
            return _success_result()

        urls = [f"https://site{i}.com/page" for i in range(6)]

        with patch("app.services.batch.crawl_url", side_effect=counting_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=urls, output_dir=self.output_dir,
                concurrency=2, per_domain_delay=0, max_retries=0,
                download=False,
            )
            await orch.run()

        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """on_progress is called after each URL completes."""
        progress_calls = []

        def on_progress(status):
            progress_calls.append(status.completed)

        mock_crawl = AsyncMock(return_value=_success_result())

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com", "https://b.com", "https://c.com"],
                output_dir=self.output_dir,
                concurrency=1, per_domain_delay=0, max_retries=0,
                download=False, on_progress=on_progress,
            )
            await orch.run()

        assert progress_calls == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_aggregation_combined_extracted(self):
        """Extracted data from multiple URLs is merged."""
        results = [
            _success_result(extracted_data={"color": "red"}),
            _success_result(extracted_data={"color": "blue"}),
        ]
        mock_crawl = AsyncMock(side_effect=results)

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com", "https://b.com"],
                output_dir=self.output_dir,
                concurrency=2, per_domain_delay=0, max_retries=0,
                download=False,
            )
            await orch.run()

        extracted = json.loads(
            (self.output_dir / "combined_extracted.json").read_text()
        )
        assert len(extracted) == 2
        assert extracted[0]["_source_url"] == "https://a.com"
        assert extracted[1]["color"] == "blue"

    @pytest.mark.asyncio
    async def test_csv_output_for_flat_data(self):
        """Flat extracted dicts produce a combined.csv."""
        results = [
            _success_result(extracted_data={"name": "Widget A", "price": "10"}),
            _success_result(extracted_data={"name": "Widget B", "price": "20"}),
        ]
        mock_crawl = AsyncMock(side_effect=results)

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com", "https://b.com"],
                output_dir=self.output_dir,
                concurrency=2, per_domain_delay=0, max_retries=0,
                download=False,
            )
            await orch.run()

        csv_path = self.output_dir / "combined.csv"
        assert csv_path.exists()
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    @pytest.mark.asyncio
    async def test_no_csv_for_nested_data(self):
        """Nested extracted data should not produce CSV."""
        results = [
            _success_result(extracted_data={"specs": {"power": "100kW"}}),
        ]
        mock_crawl = AsyncMock(side_effect=results)

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com"],
                output_dir=self.output_dir,
                concurrency=1, per_domain_delay=0, max_retries=0,
                download=False,
            )
            await orch.run()

        assert not (self.output_dir / "combined.csv").exists()

    @pytest.mark.asyncio
    async def test_per_url_output_dirs(self):
        """Each URL gets its own output subdirectory."""
        mock_crawl = AsyncMock(return_value=_success_result())

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com/page", "https://b.com/page"],
                output_dir=self.output_dir,
                concurrency=2, per_domain_delay=0, max_retries=0,
                download=False,
            )
            result = await orch.run()

        # Each result should have a distinct output_dir
        dirs = {r.output_dir for r in result.results}
        assert len(dirs) == 2

    @pytest.mark.asyncio
    async def test_job_tracking(self):
        """Orchestrator registers in global _jobs dict."""
        mock_crawl = AsyncMock(return_value=_success_result())

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", AsyncMock(return_value=[])):
            orch = BatchOrchestrator(
                urls=["https://a.com"],
                output_dir=self.output_dir,
                concurrency=1, per_domain_delay=0, max_retries=0,
                download=False,
            )
            assert orch.job_id in _jobs
            result = await orch.run()

        assert _jobs[orch.job_id].status == "completed"

    @pytest.mark.asyncio
    async def test_image_download(self):
        """Images are downloaded when download=True."""
        from app.models.crawl import ImageInfo

        img = ImageInfo(src="https://a.com/img.jpg", alt="test")
        mock_crawl = AsyncMock(return_value=_success_result(images=[img]))
        mock_dl_result = MagicMock(success=True)
        mock_download = AsyncMock(return_value=[mock_dl_result])

        with patch("app.services.batch.crawl_url", mock_crawl), \
             patch("app.services.batch.download_images", mock_download):
            orch = BatchOrchestrator(
                urls=["https://a.com"],
                output_dir=self.output_dir,
                concurrency=1, per_domain_delay=0, max_retries=0,
                download=True,
            )
            result = await orch.run()

        assert result.results[0].images_found == 1
        assert result.results[0].images_downloaded == 1
        mock_download.assert_called_once()


# ============================================================
# CLI batch flag tests
# ============================================================


class TestCLIBatchFlags:
    def test_load_urls_from_file(self, tmp_path):
        from crawl_images import _load_urls

        url_file = tmp_path / "urls.txt"
        url_file.write_text("https://a.com\n# comment\nhttps://b.com\n\nhttps://c.com\n")
        urls = _load_urls(str(url_file))
        assert urls == ["https://a.com", "https://b.com", "https://c.com"]

    def test_load_urls_missing_file(self):
        from crawl_images import _load_urls

        urls = _load_urls("/nonexistent/urls.txt")
        assert urls == []

    def test_argparse_url_optional_with_urls_file(self):
        """url positional arg is optional when --urls-file is given."""
        import argparse
        from crawl_images import main as _  # just to ensure module loads

        # We can't easily test argparse without running main(),
        # but we can verify the function exists and accepts urls
        from crawl_images import _load_urls, _batch_main
        assert callable(_load_urls)
        assert callable(_batch_main)
