"""MinIO object storage client for crawled images."""

from __future__ import annotations

import io
import logging
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_minio_client() -> Minio:
    """Return the singleton MinIO client, creating it if needed."""
    global _client
    if _client is None:
        _client = _create_client(get_settings())
    return _client


def _create_client(settings: Settings) -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def init_minio(settings: Settings | None = None) -> None:
    """Initialize the MinIO client and ensure the bucket exists."""
    global _client
    settings = settings or get_settings()
    _client = _create_client(settings)
    bucket = settings.minio_bucket
    try:
        if not _client.bucket_exists(bucket):
            _client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        else:
            logger.info("MinIO bucket exists: %s", bucket)
    except S3Error as e:
        logger.error("MinIO init failed: %s", e)
        raise


def upload_image(
    data: bytes,
    object_name: str,
    content_type: str = "application/octet-stream",
    *,
    bucket: str | None = None,
) -> str:
    """Upload image bytes to MinIO.

    Returns the object name (key) stored in the bucket.
    """
    client = get_minio_client()
    bucket = bucket or get_settings().minio_bucket
    client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def get_presigned_url(
    object_name: str,
    *,
    bucket: str | None = None,
    expires: timedelta = timedelta(hours=1),
) -> str:
    """Generate a presigned URL for downloading an image."""
    client = get_minio_client()
    bucket = bucket or get_settings().minio_bucket
    return client.presigned_get_object(bucket, object_name, expires=expires)


def list_objects(
    prefix: str = "",
    *,
    bucket: str | None = None,
) -> list[dict]:
    """List objects in the bucket with an optional prefix filter."""
    client = get_minio_client()
    bucket = bucket or get_settings().minio_bucket
    results = []
    for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
        results.append({
            "name": obj.object_name,
            "size": obj.size,
            "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
            "content_type": obj.content_type,
        })
    return results


def delete_object(
    object_name: str,
    *,
    bucket: str | None = None,
) -> None:
    """Delete an object from the bucket."""
    client = get_minio_client()
    bucket = bucket or get_settings().minio_bucket
    client.remove_object(bucket, object_name)
