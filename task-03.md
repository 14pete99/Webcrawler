# Task 03: Network Layer — TLS Fingerprint Rotation & Proxy Metadata

## Phase 2 — Requires optional `curl_cffi` dependency.

## New File: `app/stealth/tls.py`

TLS profile pool matched to user-agents.

```python
@dataclass
class TLSProfile:
    browser: str          # "chrome_124", "firefox_125", "edge_124"
    ja3_hash: str         # for reference/logging
    impersonate: str      # curl_cffi impersonate string, e.g. "chrome124"
```

- `_TLS_PROFILES`: list of 6-8 `TLSProfile` entries covering Chrome, Firefox, Edge versions matching `user_agent.py` pool.
- `pick_tls_profile(user_agent: str) -> TLSProfile` — Parses UA to identify browser family/version, picks matching profile. Falls back to Chrome if no match.

## New File: `app/services/http_client.py`

Factory abstracting the HTTP client implementation:

```python
@asynccontextmanager
async def create_stealth_client(
    stealth: StealthContext,
    proxy: str | None = None,
    timeout: float = 30,
) -> AsyncIterator[httpx.AsyncClient | curl_cffi.requests.AsyncSession]:
```

Strategy:
1. If `stealth.tls_profile` is not None and `curl_cffi` is importable → create `curl_cffi.requests.AsyncSession` with `impersonate=stealth.tls_profile.impersonate`, stealth headers, and proxy.
2. Otherwise → fall back to `httpx.AsyncClient` (current behavior).
3. Context manager handles `aclose()` on exit.

Both backends support compatible `.get(url, headers=...)` API.

## Modify: `app/services/image_downloader.py`

Replace direct `httpx.AsyncClient` construction in two locations:

- `download_image()` (line ~27): when `own_client` is True, use `create_stealth_client()`.
- `download_images()` (line ~76): replace `async with httpx.AsyncClient(...)` with `async with create_stealth_client(stealth, proxy=proxy)`.

## Modify: `app/services/proxy.py`

Add `ProxyEntry` dataclass:

```python
@dataclass
class ProxyEntry:
    url: str
    proxy_type: str = "datacenter"  # "residential" | "datacenter" | "mobile"
    country: str | None = None
    city: str | None = None
```

Update `ProxyPool`:
- Internal storage: `list[str]` → `list[ProxyEntry]`
- `from_args()` parsing: lines can be `url` or `url|type|country` (pipe-delimited). Bare URLs → `ProxyEntry(url=url)` for backward compat.
- `next()` returns `ProxyEntry | None` instead of `str | None`
- Add `next_by_type(proxy_type: str) -> ProxyEntry | None`
- Add `next_by_country(country: str) -> ProxyEntry | None`

## Modify: `app/stealth/pipeline.py`

Add to `StealthContext`:
```python
tls_profile: object | None = None  # TLSProfile
```

In `build_stealth_context()`:
```python
from .tls import pick_tls_profile
tls_profile = pick_tls_profile(ua)
```

## Modify: `app/routers/crawl.py` and `app/routers/download.py`

Update callers of `proxy_pool.next()` to use `.url` attribute:
```python
crawl_proxy = proxy_pool.next()
proxy_url = crawl_proxy.url if crawl_proxy else None
```

## Modify: `pyproject.toml`

```toml
[project.optional-dependencies]
tls = ["curl_cffi>=0.7"]
```

## Verification

1. `pip install -e .` works without `curl_cffi` (graceful fallback)
2. `pip install -e ".[tls]"` installs `curl_cffi`
3. Image downloads work with both httpx (fallback) and curl_cffi (TLS spoofing)
4. Proxy file with `url|residential|US` format parses correctly
5. `next_by_country("US")` returns only US proxies
