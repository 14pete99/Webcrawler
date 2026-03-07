"""Crawl endpoints: POST /crawl, POST /crawl/extract."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models.crawl import CrawlRequest, CrawlResponse
from ..services import crawl4ai
from ..services.image_downloader import download_images
from ..services.proxy import ProxyPool
from ..stealth.pipeline import build_stealth_context
from ..storage.profiles import get_profile

router = APIRouter(tags=["crawl"])


def _resolve_stealth(request: CrawlRequest):
    """Merge profile + inline stealth config, inline wins."""
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


@router.post("/crawl", response_model=CrawlResponse)
async def crawl_endpoint(request: CrawlRequest) -> CrawlResponse:
    """Crawl a URL and optionally download discovered images."""
    stealth = _resolve_stealth(request)
    proxy_pool = ProxyPool.from_args(request.proxy, request.proxy_file)
    crawl_proxy = proxy_pool.next()

    try:
        data = await crawl4ai.crawl_url(
            request.url,
            stealth,
            screenshot=request.screenshot,
            proxy=crawl_proxy,
            session_id=request.session_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    images = crawl4ai.extract_images(data, request.url)
    output_dir = Path(request.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = None
    if request.screenshot:
        screenshot_path = crawl4ai.extract_screenshot(data, output_dir)

    if not request.download_images or not images:
        return CrawlResponse(
            success=True,
            url=request.url,
            images_found=len(images),
            images_downloaded=0,
            screenshot_path=screenshot_path,
        )

    dl_proxy = proxy_pool.next()
    manifest, errors = await download_images(images, output_dir, stealth, proxy=dl_proxy)

    # Write manifest file
    manifest_path = output_dir / "images.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return CrawlResponse(
        success=True,
        url=request.url,
        images_found=len(images),
        images_downloaded=len(manifest),
        manifest=manifest,
        screenshot_path=screenshot_path,
        errors=errors,
    )


@router.post("/crawl/extract", response_model=CrawlResponse)
async def crawl_extract_endpoint(request: CrawlRequest) -> CrawlResponse:
    """Crawl a URL and return image metadata without downloading."""
    request.download_images = False
    return await crawl_endpoint(request)
