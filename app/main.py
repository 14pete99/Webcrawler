"""FastAPI application with routers and lifespan."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .config import get_settings
from .routers import batch, crawl, download, profiles, sessions

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure data directories exist
    settings = get_settings()
    Path(settings.profiles_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.sessions_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.default_output_dir).mkdir(parents=True, exist_ok=True)

    # Initialize MinIO storage
    try:
        from .storage.minio_store import init_minio
        init_minio(settings)
        logger.info("MinIO storage initialized (bucket: %s)", settings.minio_bucket)
    except Exception as e:
        logger.warning("MinIO not available, falling back to local storage: %s", e)

    yield


app = FastAPI(
    title="Webcrawler API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(batch.router)
app.include_router(crawl.router)
app.include_router(download.router)
app.include_router(profiles.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
