"""Application configuration via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    crawl4ai_api: str = "http://localhost:11235"
    default_output_dir: str = "./output"
    profiles_dir: str = "data/profiles"
    sessions_dir: str = "data/sessions"
    captcha_api_key: str | None = None
    captcha_provider: str = "2captcha"  # "2captcha" | "anticaptcha"

    # MinIO object storage
    minio_endpoint: str = "localhost:9002"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "crawled-images"
    minio_secure: bool = False

    model_config = {"env_prefix": "CRAWLER_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
