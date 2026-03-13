# Webcrawler User Guide

A web crawler and data extraction toolkit with advanced anti-detection, batch processing, and structured data extraction. Built on top of the [crawl4ai](https://github.com/unclecode/crawl4ai) headless browser engine.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [CLI Reference](#2-cli-reference)
3. [Single URL Crawling](#3-single-url-crawling)
4. [Data Extraction](#4-data-extraction)
5. [Batch Crawling](#5-batch-crawling)
6. [Cookie Injection & CAPTCHA Bypass](#6-cookie-injection--captcha-bypass)
7. [Stealth & Anti-Detection](#7-stealth--anti-detection)
8. [Proxy Support](#8-proxy-support)
9. [REST API](#9-rest-api)
10. [Image Downloading & Compliance](#10-image-downloading--compliance)
11. [Session Management](#11-session-management)
12. [Stealth Profiles](#12-stealth-profiles)
13. [Data Processing Scripts](#13-data-processing-scripts)
14. [Docker Deployment](#14-docker-deployment)
15. [Configuration Reference](#15-configuration-reference)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Getting Started

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- (Optional) Microsoft Edge browser installed — for `export_cookies.py`
- (Optional) Playwright — `pip install playwright && playwright install`

### Installation

```bash
# Clone the repo
git clone https://github.com/14pete99/Webcrawler.git
cd Webcrawler

# Install Python dependencies
pip install -e .

# Start the crawl4ai Docker service
docker compose up -d
```

This starts two services:
- **crawl4ai** on port `11235` — the headless browser engine
- **minio** on port `9002` (API) / `9003` (console) — optional image storage

### Quick Start

```bash
# Crawl a URL and download all images
python crawl_images.py https://example.com

# Extract page content as markdown (no image downloads)
python crawl_images.py https://example.com --extract raw --include-markdown --extract-only

# Batch crawl a list of URLs
python crawl_images.py --urls-file urls.txt --extract raw --include-markdown --extract-only
```

---

## 2. CLI Reference

```
python crawl_images.py [url] [options]
```

The `url` positional argument is optional when `--urls-file` is provided.

### All Flags

| Flag | Default | Description |
|------|---------|-------------|
| `url` | — | URL to crawl (optional if `--urls-file` given) |
| `--output-dir DIR` | `./output` | Directory for output files |
| `--screenshot` | off | Capture a rendered screenshot |
| `--proxy URL` | — | Single proxy URL |
| `--proxy-file FILE` | — | File with one proxy per line (rotating) |
| `--profile ID` | — | Stealth profile id to load |
| `--delay MIN-MAX` | — | Delay range in ms (e.g. `1000-3000`) |
| `--session-id ID` | — | Session id for cookie persistence |
| `--cookies FILE` | — | Cookie file (JSON or Netscape format) |
| `--cloudflare-bypass` | off | Detect and bypass Cloudflare challenges |
| `--captcha-solving` | off | Enable external CAPTCHA solver |
| **Extraction** | | |
| `--extract STRATEGY` | — | `raw`, `css`, `json-css`, or `regex` |
| `--selector RULE` | — | CSS selector: `name:selector` or `name:selector@attr` (repeatable) |
| `--json-schema FILE` | — | Path to JSON schema file |
| `--regex RULE` | — | Regex: `name:pattern` (repeatable) |
| `--wait-for SELECTOR` | — | Wait for CSS selector before extracting |
| `--wait-timeout SEC` | `10.0` | Wait timeout in seconds |
| `--delay-before-extract SEC` | — | Extra delay for JS rendering |
| `--include-html` | off | Save raw HTML |
| `--include-markdown` | off | Save markdown conversion |
| `--action ACTION` | — | Pre-extraction action (repeatable) |
| `--extract-only` | off | Skip image downloads |
| **Batch** | | |
| `--urls-file FILE` | — | Text file with URLs (enables batch mode) |
| `--concurrency N` | `3` | Max parallel crawls (1-20) |
| `--per-domain-delay SEC` | `2.0` | Seconds between same-domain requests |
| `--max-retries N` | `2` | Max retries per URL (0-5) |

---

## 3. Single URL Crawling

### Basic Image Crawl

Download all images found on a page:

```bash
python crawl_images.py https://example.com/gallery
```

Output:
```
output/
  images.json          # manifest of all downloaded images
  image1.jpg
  image2.png
  ...
```

### With Screenshot

```bash
python crawl_images.py https://example.com --screenshot
```

Saves a full-page screenshot alongside the images.

### Custom Output Directory

```bash
python crawl_images.py https://example.com --output-dir ./my-crawl
```

---

## 4. Data Extraction

The `--extract` flag enables structured data extraction from crawled pages. Four strategies are available.

### Strategy: `raw`

Returns the full page content as markdown and/or HTML without any selector-based extraction.

```bash
# Get markdown version of the page
python crawl_images.py https://example.com \
  --extract raw \
  --include-markdown \
  --extract-only

# Get both markdown and HTML
python crawl_images.py https://example.com \
  --extract raw \
  --include-markdown \
  --include-html \
  --extract-only
```

Output files:
- `output/page.md` — markdown conversion of the page
- `output/page.html` — raw HTML (if `--include-html`)

### Strategy: `css`

Extract specific elements using CSS selectors:

```bash
# Extract all article titles and links
python crawl_images.py https://news.example.com \
  --extract css \
  --selector "titles:h2.article-title" \
  --selector "links:a.article-link@href" \
  --extract-only
```

The `--selector` format is `name:css-selector` for text content, or `name:css-selector@attribute` to extract an HTML attribute (like `href` or `src`).

Output: `output/extracted.json`

### Strategy: `json-css`

Extract repeating structured blocks (product cards, table rows, search results). Provide a JSON schema file:

```json
{
  "base_selector": ".product-card",
  "fields": [
    {"name": "title", "selector": "h3.name"},
    {"name": "price", "selector": ".price"},
    {"name": "image", "selector": "img@src", "attribute": "src"},
    {"name": "link", "selector": "a@href", "attribute": "href"}
  ]
}
```

```bash
python crawl_images.py https://shop.example.com/products \
  --extract json-css \
  --json-schema schema.json \
  --extract-only
```

### Strategy: `regex`

Apply regex patterns against the raw HTML:

```bash
python crawl_images.py https://example.com \
  --extract regex \
  --regex "emails:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" \
  --regex "phones:\+?\d[\d\s\-]{8,}\d" \
  --extract-only
```

### Pre-Extraction Page Actions

For pages that require interaction before content is visible (tabs, expandable sections, lazy loading), use `--action`:

```bash
# Click a tab, then extract
python crawl_images.py https://example.com/product \
  --extract raw \
  --include-markdown \
  --action "click:.tab-specifications" \
  --action "wait:.specs-content" \
  --extract-only

# Scroll to trigger lazy loading
python crawl_images.py https://example.com/infinite-feed \
  --extract raw \
  --include-markdown \
  --action "scroll" \
  --extract-only

# Run custom JavaScript
python crawl_images.py https://example.com/spa \
  --extract raw \
  --include-markdown \
  --action "js:document.querySelector('.load-more').click()" \
  --extract-only
```

Action types:
| Action | Format | Description |
|--------|--------|-------------|
| `click` | `click:.selector` | Click an element |
| `wait` | `wait:.selector` | Wait for an element to appear |
| `scroll` | `scroll` | Scroll to bottom of page |
| `js` | `js:code` | Execute arbitrary JavaScript |

You can append a wait time in ms: `click:.tab:2000` (wait 2 seconds after clicking).

### Waiting for Dynamic Content

For single-page apps or server-side rendered content:

```bash
# Wait for a specific element before extracting
python crawl_images.py https://spa.example.com \
  --extract raw \
  --include-markdown \
  --wait-for ".main-content" \
  --wait-timeout 15 \
  --extract-only

# Add extra delay for JS frameworks to finish rendering
python crawl_images.py https://react-app.example.com \
  --extract raw \
  --include-markdown \
  --delay-before-extract 3.0 \
  --extract-only
```

---

## 5. Batch Crawling

Crawl multiple URLs with concurrency control, per-domain rate limiting, automatic retry, and result aggregation.

### URL File Format

Create a text file with one URL per line. Blank lines and lines starting with `#` are ignored:

```text
# Product pages to scrape
https://example.com/product/1
https://example.com/product/2
https://example.com/product/3

# Competitor pages
https://competitor.com/product/a
https://competitor.com/product/b
```

### Running a Batch Crawl

```bash
python crawl_images.py \
  --urls-file urls.txt \
  --extract raw \
  --include-markdown \
  --extract-only \
  --concurrency 3 \
  --per-domain-delay 2.0 \
  --max-retries 2 \
  --output-dir ./output/my-batch
```

### Batch Options

| Option | Default | Description |
|--------|---------|-------------|
| `--concurrency N` | 3 | Max simultaneous crawls (1-20) |
| `--per-domain-delay SEC` | 2.0 | Minimum seconds between requests to the same domain |
| `--max-retries N` | 2 | Retry failed URLs up to N times with exponential backoff |

### How It Works

1. **Concurrency**: An asyncio semaphore limits how many URLs are crawled simultaneously
2. **Rate limiting**: A per-domain lock ensures requests to the same domain are spaced by `per-domain-delay` seconds
3. **Retry**: Failed URLs are retried with exponential backoff: 2s, 4s, 8s... (capped at 30s)
4. **Progress**: Real-time progress output shows completed/total, success/fail counts

### Output Structure

```
output/my-batch/
  combined.json                    # Array of all URL results
  combined_extracted.json          # Merged extracted data (with _source_url)
  combined.csv                     # CSV version (if data is tabular)
  example.com/
    0000/                          # Per-URL subdirectory (index in URL list)
      page.md                      # Markdown
      page.html                    # HTML (if --include-html)
      extracted.json               # Extracted data
      links.json                   # Links found
    0001/
      ...
  competitor.com/
    0002/
      ...
```

### Batch with Extraction

```bash
# Scrape product data from multiple pages
python crawl_images.py \
  --urls-file product-urls.txt \
  --extract json-css \
  --json-schema product-schema.json \
  --extract-only \
  --output-dir ./output/products
```

### Batch with Cookies (Authenticated Crawling)

```bash
python crawl_images.py \
  --urls-file urls.txt \
  --cookies cookies.json \
  --extract raw \
  --include-markdown \
  --extract-only
```

---

## 6. Cookie Injection & CAPTCHA Bypass

### Exporting Cookies

For sites protected by CAPTCHA (DataDome, Cloudflare, etc.), use `export_cookies.py` to manually solve the challenge and export the resulting cookies:

```bash
python export_cookies.py https://protected-site.com \
  --output cookies.json \
  --wait-for ".main-content" \
  --timeout 120
```

This opens a visible Edge browser window. Solve any CAPTCHA manually, then the script exports all cookies when the page loads.

| Flag | Default | Description |
|------|---------|-------------|
| `url` | — | URL to open |
| `--output`, `-o` | `cookies.json` | Output file path |
| `--wait-for` | `body` | CSS selector indicating the real page has loaded |
| `--timeout` | `120` | Seconds to wait before exporting anyway |

The script uses your system's Microsoft Edge browser (`channel="msedge"`) to avoid bot detection. Edge has a genuine browser fingerprint that services like DataDome won't flag.

### Using Exported Cookies

Pass the cookie file to any crawl command:

```bash
# Single URL with cookies
python crawl_images.py https://protected-site.com/data \
  --cookies cookies.json \
  --extract raw --include-markdown --extract-only

# Batch with cookies
python crawl_images.py \
  --urls-file urls.txt \
  --cookies cookies.json \
  --extract raw --include-markdown --extract-only
```

### Supported Cookie Formats

1. **JSON array** (from browser extensions like EditThisCookie or `export_cookies.py`):
```json
[
  {"name": "session_id", "value": "abc123", "domain": ".example.com", "path": "/"},
  {"name": "auth_token", "value": "xyz789", "domain": ".example.com", "path": "/"}
]
```

2. **Netscape/curl cookie jar** (tab-separated):
```
.example.com	TRUE	/	FALSE	0	session_id	abc123
.example.com	TRUE	/	FALSE	0	auth_token	xyz789
```

### Cloudflare Bypass

For Cloudflare-protected sites, enable automatic bypass:

```bash
python crawl_images.py https://cf-protected.com \
  --cloudflare-bypass \
  --extract raw --include-markdown --extract-only
```

The system detects three types of Cloudflare challenges:
- **JS challenge** — automatic wait-based bypass
- **Turnstile CAPTCHA** — waits for token, can use external solver
- **Managed challenge** — extended wait with delayed extraction

### CAPTCHA Solving

For automated CAPTCHA solving, set up an API key:

```bash
export CRAWLER_CAPTCHA_API_KEY=your_api_key
export CRAWLER_CAPTCHA_PROVIDER=2captcha  # or "anticaptcha"
```

Then enable it:

```bash
python crawl_images.py https://captcha-site.com \
  --captcha-solving \
  --cloudflare-bypass
```

Supports reCAPTCHA, hCaptcha, Turnstile, and image CAPTCHAs.

---

## 7. Stealth & Anti-Detection

The crawler includes a comprehensive anti-detection system with multiple layers of protection.

### Default Protections (Always On)

These are enabled by default when using the `default` stealth profile:

| Feature | What It Does |
|---------|--------------|
| **Random User-Agent** | Rotates through 14 recent Chrome/Firefox/Edge user agents |
| **Realistic Headers** | Browser-specific headers (Sec-Ch-Ua, platform detection) |
| **JS Injection** | Hides `navigator.webdriver`, spoofs plugins and chrome object |
| **Random Viewport** | Picks from 11 common screen resolutions |
| **Request Delays** | 1-3 second random delays between requests |

### Browser Fingerprint Hardening

Prevents fingerprint-based tracking:

| Feature | Flag | Description |
|---------|------|-------------|
| Canvas spoofing | `canvas_spoof` | Adds per-channel noise to canvas fingerprint |
| WebGL spoofing | `webgl_spoof` | Spoofs vendor/renderer, shuffles extensions |
| Audio spoofing | `audio_spoof` | Adds sub-LSB noise to AudioContext |
| Hardware spoofing | `hardware_spoof` | Randomizes CPU cores (2-16) and memory (4-32GB) |
| Font masking | `font_mask` | Restricts font enumeration to 20 baseline fonts |

Use `fingerprint_seed` for deterministic, consistent fingerprints across sessions:

```bash
# Via CLI stealth profile or API
{"fingerprint_seed": 42}
```

### Behavioral Simulation

Simulates human-like browser behavior after page load:

| Feature | Flag | Description |
|---------|------|-------------|
| Mouse movement | `mouse_simulation` | Bezier curve mouse paths with jitter |
| Scrolling | `scroll_simulation` | Variable-speed scrolling with wheel events |
| Keyboard input | `keyboard_simulation` | Keystroke simulation with natural timing |
| Dwell time | `dwell_time` | Log-normal page dwell time (2-8 seconds) |

### Session Sophistication

| Feature | Flag | Description |
|---------|------|-------------|
| Cookie consent | `cookie_consent_dismiss` | Auto-dismisses consent banners (OneTrust, CookieBot, generic) |
| Referrer chain | `referrer_chain` | Generates plausible referrer headers (60% Google, 20% direct, etc.) |
| Delay distribution | `delay_distribution` | `uniform`, `gaussian`, `poisson`, or `lognormal` timing |
| Asset simulation | `asset_simulation` | Fetches CSS/JS assets to look like a real browser |
| Storage seeding | `storage_seed` | Pre-loads localStorage key-value pairs |

### TLS Fingerprinting

When `curl_cffi` is installed, the crawler can impersonate specific browser TLS fingerprints:

- Chrome 120/123/124
- Firefox 120/125
- Edge 124
- Safari 17

The TLS profile is automatically matched to the selected user agent.

### Geo Consistency

When using proxies, `geo_consistency: true` (default) automatically matches:
- Browser timezone to proxy country
- Browser locale/language to proxy country
- `navigator.language` and `Intl.DateTimeFormat` overrides

Supports 30+ country profiles (US, GB, AU, DE, FR, JP, etc.).

---

## 8. Proxy Support

### Single Proxy

```bash
python crawl_images.py https://example.com \
  --proxy http://user:pass@proxy-host:8080

# SOCKS5
python crawl_images.py https://example.com \
  --proxy socks5://proxy-host:1080
```

### Rotating Proxy Pool

Create a proxy file with one proxy per line:

```text
# proxies.txt - plain format
http://proxy1.example.com:8080
http://user:pass@proxy2.example.com:8080
socks5://proxy3.example.com:1080

# With metadata (pipe-delimited): url|type|country|city
http://proxy4.example.com:8080|residential|US|New York
http://proxy5.example.com:8080|datacenter|GB|London
http://proxy6.example.com:8080|mobile|DE|Berlin
```

```bash
python crawl_images.py https://example.com --proxy-file proxies.txt
```

Proxies are rotated in round-robin order. Metadata (type, country, city) enables filtering via the API.

---

## 9. REST API

Start the API server:

```bash
# Direct
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or via Docker
docker compose up -d webcrawler
```

The API is available at `http://localhost:8000` (or port `8888` via Docker).

### Endpoints

#### `POST /crawl` — Crawl and Download Images

```bash
curl -X POST http://localhost:8000/crawl \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com",
    "screenshot": true,
    "download_images": true,
    "extraction": {
      "strategy": "raw",
      "include_markdown": true
    }
  }'
```

Response:
```json
{
  "success": true,
  "url": "https://example.com",
  "images_found": 5,
  "images_downloaded": 5,
  "manifest": [...],
  "screenshot_path": "output/screenshot.png",
  "extracted_data": null,
  "markdown": "# Example Domain\n...",
  "errors": []
}
```

#### `POST /crawl/extract` — Crawl Without Downloading

Same as `/crawl` but with `download_images: false` — returns image metadata only.

```bash
curl -X POST http://localhost:8000/crawl/extract \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com"}'
```

#### `POST /crawl/extract-data` — Extract Structured Data

Optimized for data extraction. Automatically sets `download_images: false` and applies a default `raw` extraction config if none provided.

```bash
curl -X POST http://localhost:8000/crawl/extract-data \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com",
    "extraction": {
      "strategy": "css",
      "selectors": [
        {"name": "titles", "selector": "h2", "multiple": true},
        {"name": "links", "selector": "a", "attribute": "href", "multiple": true}
      ]
    }
  }'
```

#### `POST /batch/crawl` — Batch Crawl

For small batches (10 URLs or fewer), runs synchronously and returns the full result. For larger batches or when `?async=true` is passed, returns a job ID for polling.

```bash
# Synchronous (small batch)
curl -X POST http://localhost:8000/batch/crawl \
  -H 'Content-Type: application/json' \
  -d '{
    "urls": ["https://example.com", "https://httpbin.org/html"],
    "concurrency": 2,
    "per_domain_delay": 1.0,
    "extraction": {
      "strategy": "raw",
      "include_markdown": true
    }
  }'

# Asynchronous (large batch or explicit)
curl -X POST "http://localhost:8000/batch/crawl?async=true" \
  -H 'Content-Type: application/json' \
  -d '{
    "urls": ["https://site1.com", "https://site2.com", "..."],
    "concurrency": 5
  }'
```

Async response:
```json
{
  "job_id": "a1b2c3d4",
  "status": "running",
  "total": 50,
  "completed": 0,
  "progress_pct": 0.0
}
```

#### `GET /batch/{job_id}` — Poll Batch Status

```bash
curl http://localhost:8000/batch/a1b2c3d4
```

```json
{
  "job_id": "a1b2c3d4",
  "status": "completed",
  "total": 50,
  "completed": 50,
  "succeeded": 48,
  "failed": 2,
  "progress_pct": 100.0,
  "results": [...],
  "errors": ["timeout on https://..."]
}
```

#### `POST /download` — Download Specific Images

```bash
curl -X POST http://localhost:8000/download \
  -H 'Content-Type: application/json' \
  -d '{
    "images": [
      {"src": "https://example.com/img1.jpg", "alt": "Photo 1"},
      {"src": "https://example.com/img2.png", "alt": "Photo 2"}
    ],
    "output_dir": "./output/custom"
  }'
```

#### `GET /profiles` — List Stealth Profiles

```bash
curl http://localhost:8000/profiles
```

#### `POST /profiles` — Create Profile

```bash
curl -X POST http://localhost:8000/profiles \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "aggressive",
    "name": "Aggressive anti-detection",
    "config": {
      "user_agent": "random",
      "mouse_simulation": true,
      "scroll_simulation": true,
      "dwell_time": true,
      "referrer_chain": true,
      "delay_distribution": "lognormal",
      "asset_simulation": true,
      "cloudflare_bypass": true
    }
  }'
```

#### `GET /profiles/{id}` — Get Profile
#### `PUT /profiles/{id}` — Update Profile
#### `DELETE /profiles/{id}` — Delete Profile

#### `GET /sessions` — List Sessions

```bash
curl http://localhost:8000/sessions
```

#### `DELETE /sessions/{id}` — Delete Session

#### `GET /health` — Health Check

```bash
curl http://localhost:8000/health
```

---

## 10. Image Downloading & Compliance

### How Image Discovery Works

1. crawl4ai parses the page and returns all `<img>` elements with `src`, `alt`, and a relevance `score`
2. Images are downloaded with stealth headers (User-Agent, Referer, Accept)
3. Random delays are added between downloads
4. Each image is saved with its original filename (collisions get an incrementing suffix)

### Image Compliance Enforcement

All downloaded images are automatically checked against compliance limits:

| Limit | Value | Action |
|-------|-------|--------|
| Max file size | 20 MB | JPEG/WEBP: quality reduced; PNG: split into tiles |
| Max dimension | 8,000 px | Image is split into tiles |

Tile images are named: `original_tile_0_0.jpg`, `original_tile_0_1.jpg`, etc.

### MinIO Object Storage

When MinIO is running, images are automatically uploaded to object storage in addition to local files:

- **Bucket**: `crawled-images` (auto-created)
- **Object key format**: `{uuid}_{filename}`
- **Graceful fallback**: if MinIO is unavailable, images are saved locally only

Access the MinIO console at `http://localhost:9003` (credentials: `minioadmin`/`minioadmin`).

### Image Manifest

Each crawl produces an `images.json` manifest:

```json
[
  {
    "src": "https://example.com/photo.jpg",
    "file": "photo.jpg",
    "alt": "A photo",
    "extra_files": null
  },
  {
    "src": "https://example.com/huge.png",
    "file": "huge.png",
    "alt": "Large image",
    "extra_files": ["huge_tile_0_0.png", "huge_tile_0_1.png"]
  }
]
```

---

## 11. Session Management

Sessions persist cookies and browser state across crawls.

### Using Sessions

```bash
# First crawl — creates the session
python crawl_images.py https://example.com --session-id my-session

# Subsequent crawls — reuses cookies and browser context
python crawl_images.py https://example.com/page2 --session-id my-session
```

### What Sessions Store

- Cookies (domain, path, secure, httpOnly)
- Cookie count
- Browser session reference (for crawl4ai session reuse)
- Local storage key-value pairs
- Fingerprint seed (for consistent identity across requests)
- Last user agent (for consistency)

### Session Files

Sessions are stored as JSON files in `data/sessions/`:

```
data/sessions/
  my-session.json
  another-session.json
```

### API Session Management

```bash
# List all sessions
curl http://localhost:8000/sessions

# Delete a session
curl -X DELETE http://localhost:8000/sessions/my-session
```

---

## 12. Stealth Profiles

Profiles are named, reusable stealth configurations saved as JSON.

### Default Profile

The built-in `default` profile (`data/profiles/default.json`) enables:
- Random user agent and viewport
- Realistic headers
- All JS injection patches
- All fingerprint hardening (canvas, WebGL, audio, hardware, font)
- Behavioral simulation (mouse, scroll, keyboard, dwell time)
- Cookie consent dismissal
- Referrer chain generation
- Cloudflare bypass

### Using Profiles

```bash
# Use the default profile
python crawl_images.py https://example.com --profile default

# Use a custom profile
python crawl_images.py https://example.com --profile aggressive
```

### Creating Profiles via API

```bash
curl -X POST http://localhost:8000/profiles \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "minimal",
    "name": "Minimal stealth for trusted sites",
    "config": {
      "user_agent": "random",
      "headers": "minimal",
      "js_injection": false,
      "canvas_spoof": false,
      "webgl_spoof": false,
      "delay_min_ms": 500,
      "delay_max_ms": 1000
    }
  }'
```

### Profile Configuration Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user_agent` | `string\|null` | `"random"` | `"random"`, specific UA string, or `null` |
| `headers` | `string\|null` | `"realistic"` | `"realistic"` or `"minimal"` |
| `js_injection` | `bool` | `true` | Anti-detection JS patches |
| `viewport` | `string\|null` | `"random"` | `"random"`, `"1920x1080"`, or `null` |
| `delay_min_ms` | `int` | `1000` | Min delay between requests (ms) |
| `delay_max_ms` | `int` | `3000` | Max delay between requests (ms) |
| `canvas_spoof` | `bool` | `true` | Canvas fingerprint noise |
| `webgl_spoof` | `bool` | `true` | WebGL vendor/renderer spoofing |
| `audio_spoof` | `bool` | `true` | AudioContext fingerprint noise |
| `hardware_spoof` | `bool` | `true` | CPU/memory spoofing |
| `font_mask` | `bool` | `true` | Font enumeration masking |
| `fingerprint_seed` | `int\|null` | `null` | Deterministic fingerprint seed |
| `mouse_simulation` | `bool` | `false` | Post-load mouse movement |
| `scroll_simulation` | `bool` | `false` | Post-load scrolling |
| `keyboard_simulation` | `bool` | `false` | Keystroke simulation |
| `dwell_time` | `bool` | `false` | Random page dwell time |
| `cookie_consent_dismiss` | `bool` | `false` | Auto-dismiss consent banners |
| `referrer_chain` | `bool` | `false` | Plausible referrer headers |
| `delay_distribution` | `string` | `"uniform"` | `uniform\|gaussian\|poisson\|lognormal` |
| `asset_simulation` | `bool` | `false` | Fetch CSS/JS assets |
| `storage_seed` | `dict\|null` | `null` | localStorage pre-seeding |
| `captcha_solving` | `bool` | `false` | External CAPTCHA solver |
| `cloudflare_bypass` | `bool` | `false` | Cloudflare challenge bypass |
| `geo_consistency` | `bool` | `true` | Match timezone/locale to proxy |

---

## 13. Data Processing Scripts

These scripts are domain-specific tools for post-processing batch crawl results. They serve as examples of how to build analysis pipelines on top of batch crawl output.

### `parse_touareg_specs.py` — Parse Vehicle Specifications

Parses markdown output from batch crawls of car specification pages (e.g., Redbook.com.au) into structured JSON and CSV.

```bash
python parse_touareg_specs.py
```

**Input**: `output/touareg-specs/combined.json` (from a batch crawl)

**Output**:
- `output/touareg-specs/all_specifications.json` — structured specs per vehicle
- `output/touareg-specs/all_specifications.csv` — tabular format

**What it extracts**:
- Vehicle name (year, make, model, variant)
- 9 specification sections: Electrical, Engine, Transmission & Drivetrain, Fuel, Steering, Wheels & Tyres, Dimensions & Weights, Warranty & Service, Safety & Security
- Flat key format: `"Section | Key"` (e.g., `"Engine | Power"`)

### `build_touareg_db.py` — Build SQLite Database

Creates a normalized SQLite database from parsed vehicle specifications.

```bash
python build_touareg_db.py
```

**Input**: `output/touareg-specs/combined.json` + `output/touareg-specs/all_specifications.json`

**Output**: `output/touareg-specs/touareg.db`

**Database schema**:

```sql
-- Core vehicle identity
vehicles (
  id, year, variant, vehicle_name, url, badge, series,
  body_type, doors, seats, transmission, drive_type,
  fuel_type, ron_rating, release_date, country_of_origin,
  price_when_new
)

-- Key-value spec data per vehicle
specs (
  id, vehicle_id, section, key, value, numeric_value, unit
)

-- Pivoted summary view with key specs
vehicle_summary (
  id, year, variant, vehicle_name, badge, series,
  price_when_new, fuel_type, drive_type, power, power_kw,
  torque, torque_nm, engine_size, cylinders, accel_0_100,
  fuel_combined, co2_combined, kerb_weight, length_mm,
  towing_braked_kg, gears, battery_capacity, ev_range_wltp,
  front_tyres, ancap_rating
)
```

**Example queries**:

```sql
-- Most powerful vehicles
SELECT vehicle_name, value AS power
FROM specs JOIN vehicles ON vehicles.id = specs.vehicle_id
WHERE key = 'Power' AND section = 'Engine'
ORDER BY numeric_value DESC LIMIT 5;

-- Price evolution by year
SELECT year, MIN(price_when_new) AS cheapest, vehicle_name
FROM vehicles WHERE price_when_new IS NOT NULL
GROUP BY year ORDER BY year;

-- Compare all specs for a specific vehicle
SELECT section, key, value
FROM specs WHERE vehicle_id = 42
ORDER BY section, key;
```

---

## 14. Docker Deployment

### Full Stack

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps
```

Services:

| Service | Port | Description |
|---------|------|-------------|
| `crawl4ai` | 11235 | Headless browser engine |
| `minio` | 9002 (API), 9003 (console) | Image object storage |
| `webcrawler` | 8888 | FastAPI application |

### Using the Dockerized API

```bash
# Health check
curl http://localhost:8888/health

# Crawl a URL
curl -X POST http://localhost:8888/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com"}'
```

### Environment Variables

Set these in `.env` or pass to `docker compose`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRAWLER_CRAWL4AI_API` | `http://crawl4ai:11235` | crawl4ai API URL |
| `CRAWLER_DEFAULT_OUTPUT_DIR` | `./output` | Default output directory |
| `CRAWLER_PROFILES_DIR` | `data/profiles` | Stealth profiles directory |
| `CRAWLER_SESSIONS_DIR` | `data/sessions` | Sessions directory |
| `CRAWLER_CAPTCHA_API_KEY` | — | 2Captcha or Anti-Captcha API key |
| `CRAWLER_CAPTCHA_PROVIDER` | `2captcha` | `2captcha` or `anticaptcha` |
| `CRAWLER_MINIO_ENDPOINT` | `localhost:9002` | MinIO API endpoint |
| `CRAWLER_MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `CRAWLER_MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `CRAWLER_MINIO_BUCKET` | `crawled-images` | MinIO bucket name |
| `CRAWLER_MINIO_SECURE` | `false` | Use HTTPS for MinIO |

---

## 15. Configuration Reference

### `app/config.py` — Application Settings

All settings can be overridden via environment variables prefixed with `CRAWLER_`:

```python
crawl4ai_api = "http://localhost:11235"     # CRAWLER_CRAWL4AI_API
default_output_dir = "./output"              # CRAWLER_DEFAULT_OUTPUT_DIR
profiles_dir = "data/profiles"               # CRAWLER_PROFILES_DIR
sessions_dir = "data/sessions"               # CRAWLER_SESSIONS_DIR
captcha_api_key = None                       # CRAWLER_CAPTCHA_API_KEY
captcha_provider = "2captcha"                # CRAWLER_CAPTCHA_PROVIDER
minio_endpoint = "localhost:9002"            # CRAWLER_MINIO_ENDPOINT
minio_access_key = "minioadmin"              # CRAWLER_MINIO_ACCESS_KEY
minio_secret_key = "minioadmin"              # CRAWLER_MINIO_SECRET_KEY
minio_bucket = "crawled-images"              # CRAWLER_MINIO_BUCKET
minio_secure = False                         # CRAWLER_MINIO_SECURE
```

### Extraction Config (API Body)

```json
{
  "extraction": {
    "strategy": "raw|css|json-css|regex",
    "selectors": [
      {"name": "field_name", "selector": "css-selector", "attribute": "href|src|null", "multiple": true}
    ],
    "schema": {
      "base_selector": ".item",
      "fields": [
        {"name": "title", "selector": "h3"}
      ]
    },
    "patterns": {"name": "regex_pattern"},
    "pre_actions": [
      {"action": "click|wait|scroll|js", "selector": ".btn", "value": "js code", "wait_after": 1000}
    ],
    "wait_for_selector": ".content",
    "wait_timeout": 10.0,
    "delay_before_extract": 2.0,
    "include_html": false,
    "include_markdown": true,
    "include_links": false
  }
}
```

---

## 16. Troubleshooting

### crawl4ai is not running

```bash
docker compose up -d crawl4ai
docker compose logs crawl4ai
```

Ensure port 11235 is not in use by another process.

### CAPTCHA / Bot Detection

1. Export cookies manually:
   ```bash
   python export_cookies.py https://protected-site.com -o cookies.json
   ```
2. Use the cookies in your crawl:
   ```bash
   python crawl_images.py https://protected-site.com --cookies cookies.json ...
   ```

### Cloudflare Challenges

Enable `--cloudflare-bypass` and, if needed, `--captcha-solving` with an API key:

```bash
export CRAWLER_CAPTCHA_API_KEY=your_key
python crawl_images.py https://cf-site.com --cloudflare-bypass --captcha-solving
```

### Rate Limiting / 429 Errors

Increase the delay between requests:

```bash
# Single URL
python crawl_images.py https://example.com --delay 3000-5000

# Batch
python crawl_images.py --urls-file urls.txt --per-domain-delay 5.0 --concurrency 1
```

### Images Not Downloading

- Check if the site requires cookies: use `--cookies`
- Check if images are lazy-loaded: use `--action "scroll"` to trigger loading
- Check if images are behind a CDN that blocks direct access
- Use `--extract-only` first to verify the crawl succeeds

### Windows-Specific Issues

- **CSV double line breaks**: Already fixed — the batch system uses `write_bytes()` to prevent `\r\n` doubling
- **Unicode console errors**: Some pages contain Unicode characters that Windows console can't display. Output is still saved correctly to files
- **Path separators**: Use forward slashes in CLI arguments (the system handles conversion)

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_batch.py -v

# Skip integration tests (require Docker services)
python -m pytest tests/ -v --ignore=tests/test_crawl_images.py --ignore=tests/test_minio_integration.py
```
