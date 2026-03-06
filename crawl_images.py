"""
Crawl a URL with crawl4ai and save images as separate files.

Usage:
    python crawl_images.py <url> [--output-dir ./output] [--screenshot]
"""

import argparse
import base64
import hashlib
import itertools
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

CRAWL4AI_API = os.getenv("CRAWL4AI_API", "http://localhost:11235")


def load_proxies(proxy: str | None, proxy_file: str | None) -> list[str]:
    """Load proxy list from arguments. Returns list of proxy URLs."""
    proxies = []
    if proxy:
        proxies.append(proxy)
    if proxy_file:
        with open(proxy_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    proxies.append(line)
    return proxies


def make_proxy_cycle(proxies: list[str]):
    """Return an infinite cycling iterator over proxies, or None if empty."""
    if not proxies:
        return None
    return itertools.cycle(proxies)


def get_proxy_dict(proxy: str) -> dict:
    """Convert a proxy URL string to a requests-compatible proxy dict."""
    if proxy.startswith("socks"):
        return {"http": proxy, "https": proxy}
    return {"http": proxy, "https": proxy}


def crawl(url: str, screenshot: bool = False, proxy: str | None = None) -> dict:
    """Submit a crawl request and return the result."""
    params = {
        "cache_mode": "bypass",
        "wait_for_images": True,
        "exclude_external_images": False,
    }
    if screenshot:
        params["screenshot"] = True
        params["screenshot_wait_for"] = 2.0

    browser_params = {"headless": True}
    if proxy:
        browser_params["proxy"] = proxy

    payload = {
        "urls": [url],
        "browser_config": {
            "type": "BrowserConfig",
            "params": browser_params,
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": params,
        },
    }
    resp = requests.post(f"{CRAWL4AI_API}/crawl", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def download_image(src: str, output_dir: Path, proxy: str | None = None) -> str | None:
    """Download a single image and return the local filename."""
    try:
        proxies = get_proxy_dict(proxy) if proxy else None
        resp = requests.get(src, timeout=30, stream=True, proxies=proxies)
        resp.raise_for_status()

        # Derive filename from URL path, fall back to hash
        parsed = urlparse(src)
        name = os.path.basename(parsed.path)
        if not name or not re.search(r"\.\w{2,5}$", name):
            ext = resp.headers.get("content-type", "image/png").split("/")[-1]
            ext = ext.split(";")[0].strip()
            if ext == "jpeg":
                ext = "jpg"
            name = hashlib.md5(src.encode()).hexdigest()[:12] + f".{ext}"

        dest = output_dir / name
        # Avoid overwriting: append suffix if needed
        counter = 1
        while dest.exists():
            stem = dest.stem.rstrip("0123456789").rstrip("_")
            dest = output_dir / f"{stem}_{counter}{dest.suffix}"
            counter += 1

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        print(f"  Saved: {dest.name} ({dest.stat().st_size:,} bytes)")
        return str(dest)
    except Exception as e:
        print(f"  Failed to download {src}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Crawl a URL and save images as separate files")
    parser.add_argument("url", help="URL to crawl")
    parser.add_argument("--output-dir", default="./output", help="Directory to save images (default: ./output)")
    parser.add_argument("--screenshot", action="store_true", help="Also capture a rendered screenshot of the page")
    parser.add_argument("--proxy", help="Proxy URL (e.g. http://user:pass@host:port or socks5://host:port)")
    parser.add_argument("--proxy-file", help="File with one proxy URL per line (rotates through them)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    proxies = load_proxies(args.proxy, args.proxy_file)
    proxy_pool = make_proxy_cycle(proxies)
    if proxies:
        print(f"Using {len(proxies)} proxy/proxies (rotating)")

    # Pick first proxy for the crawl request
    crawl_proxy = next(proxy_pool) if proxy_pool else None

    print(f"Crawling: {args.url}")
    data = crawl(args.url, screenshot=args.screenshot, proxy=crawl_proxy)

    # Extract results - API may return list or single result
    results = data.get("results", data.get("result", []))
    if not isinstance(results, list):
        results = [results]

    all_images = []
    for result in results:
        if not result or not result.get("success"):
            print(f"Crawl failed: {result.get('error', 'unknown error')}")
            continue

        # Save screenshot if requested
        screenshot_b64 = result.get("screenshot")
        if screenshot_b64:
            screenshot_path = output_dir / "screenshot.png"
            screenshot_bytes = base64.b64decode(screenshot_b64)
            with open(screenshot_path, "wb") as f:
                f.write(screenshot_bytes)
            print(f"Screenshot saved: {screenshot_path} ({len(screenshot_bytes):,} bytes)")

        media = result.get("media", {})
        images = media.get("images", [])
        print(f"Found {len(images)} images")

        for img in images:
            src = img.get("src", "")
            if not src or src.startswith("data:"):
                continue
            # Resolve relative URLs
            if not src.startswith(("http://", "https://")):
                src = urljoin(args.url, src)
            all_images.append({"src": src, "alt": img.get("alt", ""), "score": img.get("score", 0)})

    if not all_images:
        print("No downloadable images found.")
        return

    print(f"\nDownloading {len(all_images)} images to {output_dir}/")
    saved = []
    for img in all_images:
        dl_proxy = next(proxy_pool) if proxy_pool else None
        path = download_image(img["src"], output_dir, proxy=dl_proxy)
        if path:
            saved.append({"file": path, "alt": img["alt"], "src": img["src"]})

    # Write manifest for reference
    manifest_path = output_dir / "images.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2)

    print(f"\nDone: {len(saved)}/{len(all_images)} images saved")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
