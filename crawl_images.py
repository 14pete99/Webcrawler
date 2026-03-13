"""
Crawl a URL with crawl4ai and save images as separate files.

Usage:
    python crawl_images.py <url> [--output-dir ./output] [--screenshot]
                                 [--profile default] [--delay 1000-3000]
                                 [--session-id my-session]
                                 [--proxy URL] [--proxy-file FILE]
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.models.extraction import ExtractionConfig, ExtractionSelector, JsonCssSchema, PageAction
from app.models.stealth import StealthConfig
from app.services.crawl4ai import crawl_url
from app.services.image_downloader import download_images
from app.services.proxy import ProxyPool
from app.stealth.pipeline import build_stealth_context
from app.storage.profiles import get_profile


def _build_config(args) -> StealthConfig:
    """Build a StealthConfig from CLI args, optionally merging with a profile."""
    config = StealthConfig()
    if args.profile:
        profile = get_profile(args.profile)
        if profile:
            config = profile.config.model_copy()
            print(f"Loaded profile: {args.profile}")
        else:
            print(f"Warning: profile '{args.profile}' not found, using defaults")

    if args.delay:
        parts = args.delay.split("-")
        if len(parts) == 2:
            config.delay_min_ms = int(parts[0])
            config.delay_max_ms = int(parts[1])

    if args.cloudflare_bypass:
        config.cloudflare_bypass = True
    if args.captcha_solving:
        config.captcha_solving = True

    return config


def _build_extraction(args) -> ExtractionConfig | None:
    """Build an ExtractionConfig from CLI args, or None if no extraction requested."""
    if not args.extract:
        return None

    selectors = None
    if args.selector:
        selectors = []
        for s in args.selector:
            # Format: "name:selector" or "name:selector@attr"
            name, rest = s.split(":", 1)
            attr = None
            if "@" in rest:
                sel, attr = rest.rsplit("@", 1)
            else:
                sel = rest
            selectors.append(ExtractionSelector(name=name, selector=sel, attribute=attr))

    schema = None
    if args.json_schema:
        schema_data = json.loads(Path(args.json_schema).read_text(encoding="utf-8"))
        schema = JsonCssSchema(**schema_data)

    patterns = None
    if args.regex:
        patterns = {}
        for r in args.regex:
            name, pattern = r.split(":", 1)
            patterns[name] = pattern

    pre_actions = None
    if args.action:
        pre_actions = []
        for a in args.action:
            # Format: "action:selector" or "action:selector:wait_ms"
            # Examples: "click:.tab-specs" "wait:#content" "js:document.querySelector('.expand').click()"
            parts = a.split(":", 1)
            action_type = parts[0]
            rest = parts[1] if len(parts) > 1 else None
            wait_after = 1000
            selector = None
            value = None
            if rest and ":" in rest and action_type != "js":
                rest, wait_str = rest.rsplit(":", 1)
                if wait_str.isdigit():
                    wait_after = int(wait_str)
            if action_type == "js":
                value = rest
            else:
                selector = rest
            pre_actions.append(PageAction(
                action=action_type, selector=selector, value=value, wait_after=wait_after,
            ))

    return ExtractionConfig(
        strategy=args.extract,
        selectors=selectors,
        schema=schema,
        patterns=patterns,
        pre_actions=pre_actions,
        wait_for_selector=args.wait_for,
        wait_timeout=args.wait_timeout,
        delay_before_extract=args.delay_before_extract,
        include_html=args.include_html,
        include_markdown=args.include_markdown,
    )


def _load_cookies(cookie_path: str) -> list[dict] | None:
    """Load cookies from a JSON file (browser export format).

    Supports two formats:
    - Array of cookie objects (e.g. from EditThisCookie or browser devtools)
    - Netscape/curl cookie jar (text lines with tab-separated fields)

    Returns list of dicts with name, value, domain, path fields
    suitable for crawl4ai browser_config.cookies.
    """

    path = Path(cookie_path)
    if not path.exists():
        print(f"Warning: cookie file not found: {cookie_path}")
        return None

    text = path.read_text(encoding="utf-8").strip()

    # Try JSON first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            cookies = []
            for c in data:
                cookie = {
                    "name": c.get("name", c.get("Name", "")),
                    "value": c.get("value", c.get("Value", "")),
                    "domain": c.get("domain", c.get("Domain", "")),
                    "path": c.get("path", c.get("Path", "/")),
                }
                if not cookie["name"]:
                    continue
                cookies.append(cookie)
            return cookies if cookies else None
    except (json.JSONDecodeError, ValueError):
        pass

    # Try Netscape cookie jar format (tab-separated)
    cookies = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies.append({
                "name": parts[5],
                "value": parts[6],
                "domain": parts[0],
                "path": parts[2],
            })
    return cookies if cookies else None


async def _main(args) -> None:
    config = _build_config(args)
    stealth = build_stealth_context(config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    extraction = _build_extraction(args)

    # Load cookies from file if provided
    cookies = None
    if args.cookies:
        cookies = _load_cookies(args.cookies)
        if cookies:
            print(f"Loaded {len(cookies)} cookies from {args.cookies}")

    proxy_pool = ProxyPool.from_args(args.proxy, args.proxy_file)
    if not proxy_pool.is_empty:
        print(f"Using {proxy_pool.count} proxy/proxies (rotating)")

    crawl_entry = proxy_pool.next()
    crawl_proxy = crawl_entry.url if crawl_entry else None

    print(f"Crawling: {args.url}")
    data = await crawl_url(
        args.url,
        screenshot=args.screenshot,
        stealth=stealth,
        proxy=crawl_proxy,
        session_id=args.session_id,
        output_dir=output_dir,
        extraction=extraction,
        cookies=cookies,
    )

    if args.screenshot and data.get("screenshot_path"):
        print(f"Screenshot saved: {data['screenshot_path']}")

    # Extraction output
    if extraction:
        if data.get("extracted_data"):
            extracted_path = output_dir / "extracted.json"
            extracted_path.write_text(
                json.dumps(data["extracted_data"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Extracted data saved: {extracted_path}")
        if data.get("markdown"):
            md_path = output_dir / "page.md"
            md_path.write_text(data["markdown"], encoding="utf-8")
            print(f"Markdown saved: {md_path}")
        if data.get("html"):
            html_path = output_dir / "page.html"
            html_path.write_text(data["html"], encoding="utf-8")
            print(f"HTML saved: {html_path}")
        if data.get("links"):
            links_path = output_dir / "links.json"
            links_path.write_text(
                json.dumps(data["links"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Links saved: {links_path}")

    images = data.get("images", [])
    print(f"Found {len(images)} images")

    if data.get("errors"):
        for err in data["errors"]:
            print(f"  Crawl error: {err}")

    if args.extract_only:
        return

    if not images:
        print("No downloadable images found.")
        return

    dl_entry = proxy_pool.next()
    dl_proxy = dl_entry.url if dl_entry else None
    print(f"\nDownloading {len(images)} images to {output_dir}/")
    results = await download_images(images, output_dir, stealth=stealth, proxy=dl_proxy)

    errors = [r for r in results if r.error]
    successes = [r for r in results if r.file]

    for err in errors:
        print(f"  Error [{err.src}]: {err.error}")

    manifest = [r.model_dump(exclude_none=True) for r in successes]
    manifest_path = output_dir / "images.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nDone: {len(successes)}/{len(images)} images saved")
    print(f"Manifest: {manifest_path}")


def _load_urls(file_path: str) -> list[str]:
    """Load URLs from a text file (one per line, ignoring blanks and comments)."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: URL file not found: {file_path}")
        return []
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


async def _batch_main(args, urls: list[str]) -> None:
    from app.services.batch import BatchOrchestrator

    config = _build_config(args)
    stealth = build_stealth_context(config)
    output_dir = Path(args.output_dir)
    extraction = _build_extraction(args)

    cookies = None
    if args.cookies:
        cookies = _load_cookies(args.cookies)
        if cookies:
            print(f"Loaded {len(cookies)} cookies from {args.cookies}")

    proxy_pool = ProxyPool.from_args(args.proxy, args.proxy_file)
    proxy = None
    if not proxy_pool.is_empty:
        entry = proxy_pool.next()
        proxy = entry.url if entry else None
        print(f"Using {proxy_pool.count} proxy/proxies")

    completed = 0
    total = len(urls)

    def on_progress(status):
        nonlocal completed
        completed = status.completed
        pct = status.progress_pct
        last_url = ""
        if status.results:
            for r in reversed(status.results):
                if r:
                    last_url = r.url
                    break
        ok = status.succeeded
        fail = status.failed
        print(f"  [{completed}/{total}] {pct}% — {ok} ok, {fail} failed — {last_url}")

    print(f"Batch crawl: {total} URLs, concurrency={args.concurrency}, "
          f"per-domain delay={args.per_domain_delay}s")

    orchestrator = BatchOrchestrator(
        urls=urls,
        concurrency=args.concurrency,
        per_domain_delay=args.per_domain_delay,
        max_retries=args.max_retries,
        output_dir=output_dir,
        download=not args.extract_only,
        screenshot=args.screenshot,
        extraction=extraction,
        stealth=stealth,
        proxy=proxy,
        cookies=cookies,
        on_progress=on_progress,
    )

    result = await orchestrator.run()

    print(f"\nBatch complete: {result.succeeded}/{result.total} succeeded, "
          f"{result.failed} failed")
    if result.combined_output:
        print(f"Combined output: {result.combined_output}")
    if result.errors:
        print(f"Errors ({len(result.errors)}):")
        for e in result.errors[:10]:
            print(f"  - {e}")


def main():
    parser = argparse.ArgumentParser(description="Crawl a URL and save images as separate files")
    parser.add_argument("url", nargs="?", default=None, help="URL to crawl (optional if --urls-file given)")
    parser.add_argument("--output-dir", default="./output", help="Directory to save images (default: ./output)")
    parser.add_argument("--screenshot", action="store_true", help="Also capture a rendered screenshot")
    parser.add_argument("--proxy", help="Proxy URL (e.g. http://user:pass@host:port or socks5://host:port)")
    parser.add_argument("--proxy-file", help="File with one proxy URL per line (rotates through them)")
    parser.add_argument("--profile", default=None, help="Stealth profile id to load (e.g. 'default')")
    parser.add_argument("--delay", default=None, help="Delay range in ms, e.g. '1000-3000'")
    parser.add_argument("--session-id", default=None, help="Session id for cookie persistence")
    parser.add_argument("--cookies", default=None,
                        help="Path to cookie file (JSON array or Netscape format) to inject into browser")
    parser.add_argument("--cloudflare-bypass", action="store_true", help="Detect and attempt to bypass Cloudflare challenges")
    parser.add_argument("--captcha-solving", action="store_true", help="Enable external CAPTCHA solver (requires CRAWLER_CAPTCHA_API_KEY)")

    # Extraction options
    parser.add_argument("--extract", choices=["raw", "css", "json-css", "regex"],
                        default=None, help="Extraction strategy for HTML/structured data")
    parser.add_argument("--selector", action="append",
                        help="CSS selector rule: 'name:selector' or 'name:selector@attr' (repeatable)")
    parser.add_argument("--json-schema", default=None,
                        help="Path to JSON file with JsonCssSchema definition")
    parser.add_argument("--regex", action="append",
                        help="Regex rule: 'name:pattern' (repeatable)")
    parser.add_argument("--wait-for", default=None,
                        help="CSS selector to wait for before extracting (SSR support)")
    parser.add_argument("--wait-timeout", type=float, default=10.0,
                        help="Wait timeout in seconds (default: 10)")
    parser.add_argument("--delay-before-extract", type=float, default=None,
                        help="Extra delay in seconds for JS rendering")
    parser.add_argument("--include-html", action="store_true",
                        help="Save raw HTML to output")
    parser.add_argument("--include-markdown", action="store_true",
                        help="Save markdown to output")
    parser.add_argument("--action", action="append",
                        help="Pre-extraction action: 'click:.selector' 'wait:.selector' 'js:code' (repeatable)")
    parser.add_argument("--extract-only", action="store_true",
                        help="Skip image download, only extract data")

    # Batch options
    parser.add_argument("--urls-file", default=None,
                        help="Text file with one URL per line (enables batch mode)")
    parser.add_argument("--concurrency", type=int, default=3,
                        help="Max parallel crawls in batch mode (default: 3)")
    parser.add_argument("--per-domain-delay", type=float, default=2.0,
                        help="Seconds between requests to same domain (default: 2.0)")
    parser.add_argument("--max-retries", type=int, default=2,
                        help="Max retry attempts per URL in batch mode (default: 2)")
    args = parser.parse_args()

    if not args.url and not args.urls_file:
        parser.error("either url or --urls-file is required")

    if args.urls_file:
        urls = _load_urls(args.urls_file)
        if not urls:
            parser.error(f"no URLs found in {args.urls_file}")
        asyncio.run(_batch_main(args, urls))
    else:
        asyncio.run(_main(args))


if __name__ == "__main__":
    main()
