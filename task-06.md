# Task 06: Infrastructure — CAPTCHA Solving, Cloudflare Bypass & Geographic Consistency

## Phase 5 — Depends on proxy metadata (task-03) and session persistence (task-05).

## New File: `app/services/captcha.py`

CAPTCHA solver integration supporting 2Captcha and Anti-Captcha APIs.

```python
class CaptchaSolver:
    def __init__(self, api_key: str, provider: str = "2captcha"):
        self.api_key = api_key
        self.provider = provider

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:
        """Submit reCAPTCHA v2 task, poll for result, return token."""

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        """Submit hCaptcha task, poll for result, return token."""

    async def solve_turnstile(self, site_key: str, page_url: str) -> str:
        """Submit Cloudflare Turnstile task, poll for result, return token."""

    async def solve_image(self, image_b64: str) -> str:
        """Submit image CAPTCHA, poll for result, return answer text."""

    async def _submit_and_poll(self, task: dict) -> str:
        """Shared submit/poll logic. Polls every 5s, max 30s interval, 120s timeout."""
```

Uses `httpx.AsyncClient` internally.

## New File: `app/stealth/cloudflare.py`

Cloudflare challenge detection and bypass configuration.

### Functions

- `detect_cloudflare_challenge(html: str) -> bool` — Checks for markers: `"cf-browser-verification"`, `"__cf_chl_"`, `"challenges.cloudflare.com"`, `"Just a moment..."` title.

- `detect_challenge_type(html: str) -> str | None` — Returns `"js_challenge"`, `"turnstile"`, `"managed"`, or `None`.

- `build_cf_bypass_config(challenge_type: str) -> dict` — Returns crawl4ai `CrawlerRunConfig` params optimized for the challenge type:
  - Increased `page_timeout`
  - `wait_for` selector targeting challenge completion
  - `delay_before_return_html`

- `turnstile_callback_js(token: str) -> str` — JS that injects a solved Turnstile token into the page's callback.

## New File: `app/stealth/geo.py`

Geographic consistency — match timezone, locale, and languages to proxy country.

```python
@dataclass
class GeoProfile:
    country_code: str     # ISO 3166-1 alpha-2
    timezone: str         # IANA timezone, e.g. "America/New_York"
    locale: str           # e.g. "en-US"
    languages: list[str]  # e.g. ["en-US", "en"]
```

- `_GEO_MAP`: dict mapping ~30 common country codes to `GeoProfile` instances.
- `match_geo_to_proxy(proxy_entry: ProxyEntry) -> GeoProfile | None` — Looks up `proxy_entry.country` in `_GEO_MAP`.
- `geo_override_js(geo: GeoProfile) -> str` — JS overrides for:
  - `Intl.DateTimeFormat().resolvedOptions().timeZone` (via Proxy on `Intl.DateTimeFormat`)
  - `navigator.language` and `navigator.languages`
  - `Date.prototype.getTimezoneOffset()` for correct offset

## Modify: `app/config.py`

Add settings (env vars: `CRAWLER_CAPTCHA_API_KEY`, `CRAWLER_CAPTCHA_PROVIDER`):

```python
captcha_api_key: str | None = None
captcha_provider: str = "2captcha"  # "2captcha" | "anticaptcha"
```

## Modify: `app/models/stealth.py`

Add to `StealthConfig`:

```python
captcha_solving: bool = Field(default=False, description="Enable CAPTCHA solving via external API")
cloudflare_bypass: bool = Field(default=False, description="Detect and attempt to bypass Cloudflare challenges")
geo_consistency: bool = Field(default=True, description="Auto-match timezone/locale to proxy country")
```

## Modify: `app/services/crawl4ai.py`

Add Cloudflare challenge retry logic after initial crawl:

1. Extract HTML from crawl result
2. Call `detect_cloudflare_challenge(html)`
3. If detected and `cloudflare_bypass` enabled:
   - For JS challenges → retry with `build_cf_bypass_config("js_challenge")` params
   - For Turnstile → instantiate `CaptchaSolver`, call `solve_turnstile()`, inject token via `turnstile_callback_js()`, retry
4. Maximum 2 retries

Add geo handling:
```python
if stealth.geo_profile:
    browser_params["timezone_id"] = stealth.geo_profile.timezone
    browser_params["locale"] = stealth.geo_profile.locale
```

New optional parameters for `crawl_url()`:
```python
captcha_solver: CaptchaSolver | None = None,
cloudflare_bypass: bool = False,
```

## Modify: `app/stealth/pipeline.py`

Add to `StealthContext`:
```python
geo_profile: object | None = None  # GeoProfile
```

Expand `build_stealth_context` signature:
```python
def build_stealth_context(
    config: StealthConfig | None = None,
    target_url: str | None = None,
    proxy_country: str | None = None,
) -> StealthContext:
```

If `config.geo_consistency` is True and `proxy_country` is set:
- Call `match_geo_to_proxy()` → `GeoProfile`
- Append `geo_override_js(geo)` to `js_scripts`
- Set `geo_profile` on `StealthContext`

## Modify: `app/routers/crawl.py`

- Pass `proxy_country` to `build_stealth_context()` from `ProxyEntry.country`
- Instantiate `CaptchaSolver` from settings when `captcha_solving` enabled
- Pass `captcha_solver` and `cloudflare_bypass` to `crawl_url()`

## Risks

- **2Captcha latency**: 10-60s per solve. Increase crawl4ai client timeout when captcha solving enabled.
- **2Captcha cost**: Only trigger on detected challenges, never speculatively.
- **curl_cffi dependency**: Not needed for this phase but `captcha.py` uses `httpx` directly.
- **Cloudflare detection accuracy**: False positives could trigger unnecessary retries. Keep detection conservative.

## Verification

1. `detect_cloudflare_challenge()` correctly identifies CF challenge pages
2. `detect_challenge_type()` distinguishes JS challenge, Turnstile, and managed
3. `GeoProfile` mappings cover at least 30 countries with correct timezones
4. Geo JS overrides produce correct `timeZone` and `language` values
5. `CaptchaSolver` correctly submits and polls 2Captcha API (mock test)
6. Cloudflare retry logic respects max 2 retries
7. Settings load from environment variables correctly
