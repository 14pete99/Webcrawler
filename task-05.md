# Task 05: Session & Request Sophistication

## Phase 4 — Cookie consent, referrer chains, delay distributions, asset simulation, storage seeding.

## New File: `app/stealth/cookies.py`

### Functions

- `cookie_consent_js() -> str` — JS that uses `MutationObserver` to detect cookie consent dialogs. Checks for known frameworks:
  - OneTrust: `#onetrust-accept-btn-handler`
  - CookieBot: `#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll`
  - Generic: `[class*="cookie"] button[class*="accept"]`
  - Fallback: buttons containing text "Accept", "Agree", "OK" within cookie banner patterns
  - Observer watches for late-loading banners up to 5 seconds.

- `seed_storage_js(local_storage: dict[str, str] | None, session_storage: dict[str, str] | None = None) -> str` — JS that calls `localStorage.setItem(k, v)` and optionally `sessionStorage.setItem(k, v)`.

## New File: `app/stealth/referrer.py`

### Functions

- `pick_referrer(target_url: str) -> str` — Returns a plausible referrer:
  - 60% Google search: `https://www.google.com/search?q=<domain keywords>`
  - 20% direct navigation (empty string)
  - 10% social media (Twitter/Reddit)
  - 10% same domain

- `build_referrer_chain(target_url: str, depth: int = 2) -> list[str]` — Returns a sequence of URLs representing a navigation path for multi-page crawl sessions.

## New File: `app/stealth/assets.py`

### Functions

- `discover_page_assets(html: str, base_url: str) -> list[str]` — Uses regex to extract `<link rel="stylesheet" href="...">` and `<script src="...">` URLs. Resolves relative URLs against `base_url`.

- `async fetch_assets(urls: list[str], client, stealth: StealthContext, max_assets: int = 10) -> None` — Fires HEAD/GET requests for up to `max_assets` URLs with stealth delays between them. Responses are discarded. Makes traffic pattern look like a real browser loading sub-resources.

## Modify: `app/stealth/delays.py`

Expand `make_delay_fn` signature:

```python
def make_delay_fn(
    min_ms: int = 1000,
    max_ms: int = 3000,
    distribution: str = "uniform",
) -> Callable[[], float]:
```

New distributions (all clamped to [min_s, max_s]):
- `"uniform"` — current behavior (default, backward compatible)
- `"gaussian"` — `random.gauss(mu=midpoint, sigma=range/4)`
- `"poisson"` — `random.expovariate(1/midpoint)` (exponential inter-arrival)
- `"lognormal"` — `random.lognormvariate(mu=ln(midpoint), sigma=0.5)`

## Modify: `app/stealth/headers.py`

Expand `generate_headers` signature:

```python
def generate_headers(
    user_agent: str,
    strategy: str | None = "realistic",
    referrer: str | None = None,
    cache_state: dict | None = None,
) -> dict[str, str]:
```

- If `referrer` is non-empty → set `headers["Referer"] = referrer`
- If `cache_state` provided → add `If-Modified-Since` and/or `If-None-Match`

New helper:
```python
def add_conditional_headers(headers: dict, etag: str | None = None, last_modified: str | None = None) -> dict[str, str]:
```

## Modify: `app/models/stealth.py`

Add to `StealthConfig`:

```python
cookie_consent_dismiss: bool = Field(default=False, description="Auto-dismiss cookie consent banners")
referrer_chain: bool = Field(default=False, description="Generate plausible Referer headers")
delay_distribution: str = Field(default="uniform", description="Delay distribution: uniform|gaussian|poisson|lognormal")
asset_simulation: bool = Field(default=False, description="Fetch CSS/JS assets to simulate browser loading")
storage_seed: dict[str, str] | None = Field(default=None, description="Key-value pairs to seed in localStorage")
```

## Modify: `app/storage/sessions.py`

Extend persisted session structure from `{"cookies": [...]}` to:

```json
{
  "cookies": [...],
  "local_storage": {},
  "fingerprint_seed": null,
  "last_user_agent": null
}
```

Add functions:
- `save_session_profile(session_id, cookies, local_storage, fingerprint_seed) -> None`
- `get_session_profile(session_id) -> dict | None`

Existing `get_session_cookies`/`save_session_cookies` remain for backward compat, delegate internally.

## Modify: `app/models/session.py`

Extend `SessionInfo`:
```python
has_local_storage: bool = False
fingerprint_seed: int | None = None
```

## Modify: `app/stealth/pipeline.py`

- Pass `distribution=config.delay_distribution` to `make_delay_fn()`
- Add optional `target_url: str | None = None` parameter to `build_stealth_context()`
- If `config.referrer_chain` → call `pick_referrer(target_url)`, pass to `generate_headers()`
- If `config.cookie_consent_dismiss` → append `cookie_consent_js()` to `behavior_scripts` (post-load)
- If `config.storage_seed` → prepend `seed_storage_js(config.storage_seed)` to `js_scripts` (pre-load)

## Modify: `app/routers/crawl.py`

- Pass `target_url=request.url` to `build_stealth_context()`
- After main crawl, if `asset_simulation` enabled:
  1. Extract HTML from crawl results
  2. Call `discover_page_assets(html, request.url)`
  3. Call `fetch_assets()` with stealth client

## Verification

1. Cookie consent JS handles OneTrust, CookieBot, and generic selectors
2. Referrer generator produces valid Google/social/direct URLs
3. All four delay distributions produce values within configured bounds
4. Asset discovery correctly extracts stylesheet and script URLs from HTML
5. Session persistence stores and retrieves localStorage and fingerprint seed
6. Backward compat: requests without new fields work identically to before
