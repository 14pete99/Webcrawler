"""HTTP client factory — abstracts httpx vs curl_cffi backends."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

from app.stealth.pipeline import StealthContext


try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession

    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False


@asynccontextmanager
async def create_stealth_client(
    stealth: StealthContext | None = None,
    proxy: str | None = None,
    timeout: float = 30,
) -> AsyncIterator[httpx.AsyncClient]:
    """Create an HTTP client with optional TLS fingerprint impersonation.

    Strategy:
    1. If stealth.tls_profile is set and curl_cffi is available, use curl_cffi
       with TLS impersonation.
    2. Otherwise, fall back to httpx.AsyncClient.

    Both backends support a compatible .get(url, headers=...) API.
    """
    tls_profile = getattr(stealth, "tls_profile", None) if stealth else None

    if tls_profile and _HAS_CURL_CFFI:
        headers = stealth.image_headers if stealth else {}
        session = CurlAsyncSession(
            impersonate=tls_profile.impersonate,
            headers=headers,
            proxy=proxy,
            timeout=timeout,
        )
        try:
            yield session  # type: ignore[arg-type]
        finally:
            await session.close()
    else:
        transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
        async with httpx.AsyncClient(
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            yield client
