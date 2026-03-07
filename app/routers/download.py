"""Download endpoint: POST /download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from ..models.download import DownloadRequest, DownloadResponse
from ..services.image_downloader import download_images
from ..stealth.pipeline import build_stealth_context
from ..storage.profiles import get_profile

router = APIRouter(tags=["download"])


@router.post("/download", response_model=DownloadResponse)
async def download_endpoint(request: DownloadRequest) -> DownloadResponse:
    """Download a specific list of image URLs."""
    from ..models.stealth import StealthConfig

    config = StealthConfig()
    if request.profile_id:
        profile = get_profile(request.profile_id)
        if profile:
            config = profile.config.model_copy()
    if request.stealth:
        override = request.stealth.model_dump(exclude_unset=True)
        config = config.model_copy(update=override)

    stealth = build_stealth_context(config)
    output_dir = Path(request.output_dir)
    images = [img.model_dump() for img in request.images]

    manifest, errors = await download_images(
        images, output_dir, stealth, proxy=request.proxy
    )

    return DownloadResponse(
        success=len(errors) == 0,
        downloaded=len(manifest),
        failed=len(errors),
        manifest=manifest,
        errors=errors,
    )
