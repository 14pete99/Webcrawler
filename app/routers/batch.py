"""Batch crawl endpoints: POST /batch/crawl, GET /batch/{job_id}."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..models.batch import BatchCrawlRequest, BatchCrawlResponse, BatchJobStatus
from ..services.batch import BatchOrchestrator, get_job
from ..services.proxy import ProxyPool
from ..stealth.pipeline import build_stealth_context
from ..storage.profiles import get_profile

router = APIRouter(prefix="/batch", tags=["batch"])


def _resolve_batch_stealth(request: BatchCrawlRequest):
    """Resolve stealth config from profile + inline overrides."""
    from ..models.stealth import StealthConfig

    config = StealthConfig()
    if request.profile_id:
        profile = get_profile(request.profile_id)
        if profile:
            config = profile.config.model_copy()
    if request.stealth:
        override = request.stealth.model_dump(exclude_unset=True)
        config = config.model_copy(update=override)
    return build_stealth_context(config)


@router.post("/crawl", response_model=BatchCrawlResponse | BatchJobStatus)
async def batch_crawl_endpoint(
    request: BatchCrawlRequest,
    background_tasks: BackgroundTasks,
    run_async: bool = Query(default=False, alias="async"),
) -> BatchCrawlResponse | BatchJobStatus:
    """Crawl multiple URLs with concurrency control and aggregation.

    For small batches (<=10 URLs), runs synchronously by default.
    Pass ?async=true or submit >10 URLs to get a job_id for polling.
    """
    stealth = _resolve_batch_stealth(request)

    proxy_pool = ProxyPool.from_args(request.proxy, request.proxy_file)
    proxy_entry = proxy_pool.next()
    proxy = proxy_entry.url if proxy_entry else None

    # Load cookies if provided
    cookies = None
    if request.cookies_file:
        from crawl_images import _load_cookies

        cookies = _load_cookies(request.cookies_file)

    orchestrator = BatchOrchestrator(
        urls=request.urls,
        concurrency=request.concurrency,
        per_domain_delay=request.per_domain_delay,
        max_retries=request.max_retries,
        output_dir=Path(request.output_dir),
        download=request.download_images,
        screenshot=request.screenshot,
        extraction=request.extraction,
        stealth=stealth,
        proxy=proxy,
        cookies=cookies,
    )

    # Async mode for large batches or explicit request
    if run_async or len(request.urls) > 10:
        background_tasks.add_task(orchestrator.run)
        return orchestrator._status

    # Sync mode for small batches
    return await orchestrator.run()


@router.get("/{job_id}", response_model=BatchJobStatus)
async def batch_status_endpoint(job_id: str) -> BatchJobStatus:
    """Get the status of a batch crawl job."""
    status = get_job(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status
