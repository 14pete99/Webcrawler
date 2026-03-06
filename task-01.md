# Webcrawler API Restructure Plan

## Context
The project is a single-file web crawler (`crawl_images.py`, 197 lines) that calls a crawl4ai Docker service to extract and download images. The user needs anti-detection/stealth features and wants the project restructured as a FastAPI API with modular, composable components. The CLI will import modules directly (no server required for CLI use).

## Project Structure

```
e:\OneDrive\Apps\Webcrawler\
├── docker-compose.yml                # existing (crawl4ai only)
├── pyproject.toml                    # new - dependencies
├── crawl_images.py                   # rewritten as thin CLI using app modules directly
│
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app, routers, lifespan
│   ├── config.py                     # pydantic-settings: env vars, defaults
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── stealth.py                # StealthConfig, StealthProfile
│   │   ├── crawl.py                  # CrawlRequest, CrawlResponse
│   │   ├── download.py               # DownloadRequest, DownloadResponse
│   │   └── session.py                # SessionInfo
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── crawl.py                  # POST /crawl, POST /crawl/extract
│   │   ├── download.py               # POST /download
│   │   ├── profiles.py               # CRUD /profiles
│   │   └── sessions.py               # GET/DELETE /sessions
│   │
│   ├── stealth/
│   │   ├── __init__.py
│   │   ├── pipeline.py               # build_stealth_context() - composes all modules
│   │   ├── user_agent.py             # UA pool + generator
│   │   ├── headers.py                # Realistic header sets matched to UA
│   │   ├── javascript.py             # JS injection scripts (navigator.webdriver, etc.)
│   │   ├── viewport.py               # Viewport dimension pool
│   │   └── delays.py                 # Random delay generator (uniform/gaussian)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── crawl4ai.py               # Wraps crawl4ai Docker API
│   │   ├── image_downloader.py       # Async image downloads with stealth
│   │   └── proxy.py                  # ProxyPool: load, rotate, cycle
│   │
│   └── storage/
│       ├── __init__.py
│       ├── profiles.py               # JSON file CRUD for stealth profiles
│       └── sessions.py               # Cookie jar persistence per session
│
├── data/
│   ├── profiles/                     # Saved profile JSON files
│   │   └── default.json              # Ships with sensible defaults
│   └── sessions/                     # Persisted cookie jars
│
└── output/                           # existing - default download dir
```

## API Endpoints

### `POST /crawl` — Crawl + optionally download images
```json
{
  "url": "https://example.com",
  "screenshot": false,
  "output_dir": "./output",
  "download_images": true,
  "stealth": { "user_agent": "random", "headers": "realistic", "js_injection": true, "viewport": "random", "delay_min_ms": 1000, "delay_max_ms": 3000 },
  "profile_id": "default",
  "session_id": "my-session",
  "proxy": null,
  "proxy_file": null
}
```
Response: `{ success, url, images_found, images_downloaded, manifest, screenshot_path, errors }`

### `POST /crawl/extract` — Crawl only, return image metadata without downloading

### `POST /download` — Download a specific list of image URLs
```json
{
  "images": [{"src": "https://...", "alt": "..."}],
  "output_dir": "./output",
  "stealth": { ... },
  "profile_id": null,
  "session_id": null,
  "proxy": null
}
```

### `GET/POST/PUT/DELETE /profiles` — CRUD for stealth profiles
### `GET/DELETE /sessions` — Manage persistent sessions

## Stealth Pipeline Design

`pipeline.build_stealth_context(config)` calls modules in order and returns a `StealthContext`:

1. **user_agent.py** — pick UA from curated pool (Chrome/Firefox/Edge, desktop/mobile)
2. **headers.py** — generate matching headers (Accept-Language, Sec-Ch-Ua, Sec-Fetch-*, etc.)
3. **javascript.py** — JS snippets: patch `navigator.webdriver`, `navigator.plugins`, `window.chrome`
4. **viewport.py** — pick from common resolutions (1920x1080, 1366x768, etc.)
5. **delays.py** — return a callable that produces random delays per strategy

The `StealthContext` is consumed by both `crawl4ai.py` (browser-level: UA, JS, viewport) and `image_downloader.py` (HTTP-level: headers, delays).

If both `profile_id` and inline `stealth` are provided, inline values override the profile's values.

## Session Persistence

Two layers:
- **crawl4ai browser sessions**: pass `session_id` to crawl4ai so it reuses the browser context
- **HTTP download sessions**: `httpx.AsyncClient` with persistent `CookieJar` per session, serialized to `data/sessions/{id}.json`

Sessions are created lazily on first use. `DELETE /sessions/{id}` clears both layers.

## Dependencies (pyproject.toml)
```
fastapi
uvicorn[standard]
httpx[socks]          # async HTTP client, replaces requests
pydantic-settings     # config from env vars
```

## CLI Rewrite (crawl_images.py)
Thin wrapper that imports `app` modules directly (no server needed):
- Parses args (same flags as today + `--profile`, `--stealth`, `--delay`, `--session-id`)
- Calls `build_stealth_context()`, `crawl_url()`, `download_images()` directly
- ~50 lines

## Implementation Order

1. Create `pyproject.toml` and project scaffolding (`app/__init__.py`, etc.)
2. **Models** — define all Pydantic schemas (`models/`)
3. **Stealth modules** — `user_agent.py`, `headers.py`, `javascript.py`, `viewport.py`, `delays.py`, `pipeline.py`
4. **Services** — extract and enhance `proxy.py`, `crawl4ai.py`, `image_downloader.py` from current code
5. **Storage** — `profiles.py`, `sessions.py` + default profile
6. **Routers** — wire up all endpoints
7. **FastAPI app** — `main.py` with lifespan, router includes
8. **CLI rewrite** — update `crawl_images.py` to use app modules
9. **Config** — `config.py` with pydantic-settings
10. **Test** — verify end-to-end: start server, hit endpoints, run CLI

## Verification
1. `pip install -e .` installs cleanly
2. `uvicorn app.main:app` starts without errors
3. `POST /crawl` with stealth config returns images
4. `POST /crawl/extract` returns metadata without downloading
5. `POST /download` downloads specific URLs
6. `GET/POST /profiles` CRUD works
7. `python crawl_images.py <url> --profile default` works without server running
8. Proxy rotation distributes across proxies
9. Session cookies persist across multiple crawl calls with same session_id
