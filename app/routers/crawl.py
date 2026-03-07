"""Crawl endpoints: POST /crawl, POST /crawl/extract."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models.crawl import CrawlRequest, CrawlResponse
from ..services.crawl4ai import crawl_url
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
    output_dir = Path(request.output_dir)

    try:
        data = await crawl_url(
            request.url,
            screenshot=request.screenshot,
            stealth=stealth,
            proxy=crawl_proxy,
            session_id=request.session_id,
            output_dir=output_dir,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    images = data.get("images", [])
    screenshot_path = data.get("screenshot_path")
    errors = data.get("errors", [])

    if not request.download_images or not images:
        return CrawlResponse(
            success=data.get("success", True),
            url=request.url,
            images_found=len(images),
            images_downloaded=0,
            screenshot_path=screenshot_path,
            errors=errors,
        )

    dl_proxy = proxy_pool.next()
    results = await download_images(
        images, output_dir, stealth=stealth, proxy=dl_proxy, referer=request.url,
    )

    manifest = [r.model_dump() for r in results if r.file]
    dl_errors = [r.error for r in results if r.error]

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
        errors=errors + dl_errors,
    )


@router.post("/crawl/extract", response_model=CrawlResponse)
async def crawl_extract_endpoint(request: CrawlRequest) -> CrawlResponse:
    """Crawl a URL and return image metadata without downloading."""
    request.download_images = False
    return await crawl_endpoint(request)
