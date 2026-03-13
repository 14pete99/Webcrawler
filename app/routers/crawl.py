"""Crawl endpoints: POST /crawl, POST /crawl/extract, POST /crawl/extract-data."""

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


def _resolve_stealth(request: CrawlRequest, proxy_country: str | None = None):
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
    return config, build_stealth_context(config, target_url=request.url, proxy_country=proxy_country)


@router.post("/crawl", response_model=CrawlResponse)
async def crawl_endpoint(request: CrawlRequest) -> CrawlResponse:
    """Crawl a URL and optionally download discovered images."""
    proxy_pool = ProxyPool.from_args(request.proxy, request.proxy_file)
    crawl_proxy_entry = proxy_pool.next()
    crawl_proxy = crawl_proxy_entry.url if crawl_proxy_entry else None
    proxy_country = crawl_proxy_entry.country if crawl_proxy_entry else None
    stealth_config, stealth = _resolve_stealth(request, proxy_country=proxy_country)
    output_dir = Path(request.output_dir)

    # CAPTCHA solver setup
    captcha_solver = None
    if stealth_config.captcha_solving:
        from ..config import get_settings
        from ..services.captcha import CaptchaSolver

        settings = get_settings()
        if settings.captcha_api_key:
            captcha_solver = CaptchaSolver(settings.captcha_api_key, settings.captcha_provider)

    try:
        data = await crawl_url(
            request.url,
            screenshot=request.screenshot,
            stealth=stealth,
            proxy=crawl_proxy,
            session_id=request.session_id,
            output_dir=output_dir,
            captcha_solver=captcha_solver,
            cloudflare_bypass=stealth_config.cloudflare_bypass,
            extraction=request.extraction,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    images = data.get("images", [])
    screenshot_path = data.get("screenshot_path")
    errors = data.get("errors", [])

    # Extraction results (present when extraction config was provided)
    extraction_fields: dict = {}
    if data.get("extracted_data") is not None:
        extraction_fields["extracted_data"] = data["extracted_data"]
    if data.get("markdown") is not None:
        extraction_fields["markdown"] = data["markdown"]
    if data.get("html") is not None:
        extraction_fields["html"] = data["html"]
    if data.get("links") is not None:
        extraction_fields["links"] = data["links"]

    if not request.download_images or not images:
        return CrawlResponse(
            success=data.get("success", True),
            url=request.url,
            images_found=len(images),
            images_downloaded=0,
            screenshot_path=screenshot_path,
            errors=errors,
            **extraction_fields,
        )

    dl_proxy_entry = proxy_pool.next()
    dl_proxy = dl_proxy_entry.url if dl_proxy_entry else None
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
        **extraction_fields,
    )


@router.post("/crawl/extract", response_model=CrawlResponse)
async def crawl_extract_endpoint(request: CrawlRequest) -> CrawlResponse:
    """Crawl a URL and return image metadata without downloading."""
    request.download_images = False
    return await crawl_endpoint(request)


@router.post("/crawl/extract-data", response_model=CrawlResponse)
async def crawl_extract_data_endpoint(request: CrawlRequest) -> CrawlResponse:
    """Crawl a URL and return extracted HTML/structured data (no image downloads)."""
    request.download_images = False
    if request.extraction is None:
        from ..models.extraction import ExtractionConfig

        request.extraction = ExtractionConfig()
    return await crawl_endpoint(request)
