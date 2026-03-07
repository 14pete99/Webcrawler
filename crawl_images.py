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

    return config


async def _main(args) -> None:
    config = _build_config(args)
    stealth = build_stealth_context(config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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
    )

    if args.screenshot and data.get("screenshot_path"):
        print(f"Screenshot saved: {data['screenshot_path']}")

    images = data.get("images", [])
    print(f"Found {len(images)} images")

    if data.get("errors"):
        for err in data["errors"]:
            print(f"  Crawl error: {err}")

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


def main():
    parser = argparse.ArgumentParser(description="Crawl a URL and save images as separate files")
    parser.add_argument("url", help="URL to crawl")
    parser.add_argument("--output-dir", default="./output", help="Directory to save images (default: ./output)")
    parser.add_argument("--screenshot", action="store_true", help="Also capture a rendered screenshot")
    parser.add_argument("--proxy", help="Proxy URL (e.g. http://user:pass@host:port or socks5://host:port)")
    parser.add_argument("--proxy-file", help="File with one proxy URL per line (rotates through them)")
    parser.add_argument("--profile", default=None, help="Stealth profile id to load (e.g. 'default')")
    parser.add_argument("--delay", default=None, help="Delay range in ms, e.g. '1000-3000'")
    parser.add_argument("--session-id", default=None, help="Session id for cookie persistence")
    args = parser.parse_args()

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
