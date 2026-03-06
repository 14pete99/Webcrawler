"""FastAPI application with routers and lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .config import get_settings
from .routers import crawl, download, profiles, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure data directories exist
    settings = get_settings()
    Path(settings.profiles_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.sessions_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.default_output_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Webcrawler API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(crawl.router)
app.include_router(download.router)
app.include_router(profiles.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
