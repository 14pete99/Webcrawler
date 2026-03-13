"""Open a URL in a visible browser, wait for CAPTCHA to be solved, export cookies.

Usage:
    python export_cookies.py <url> [--output cookies.json] [--wait-for selector]

The script opens a Chromium browser window. Solve any CAPTCHA manually, then
the script detects when the real page loads and exports all cookies to a JSON
file compatible with --cookies flag in crawl_images.py.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path


async def main(url: str, output: str, wait_for: str | None, timeout: int):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # Use real Chrome/Edge instead of bundled Chromium to avoid bot detection.
        # channel="msedge" uses the system-installed Edge browser which has a
        # genuine browser fingerprint that DataDome/CloudFlare won't flag.
        browser = await p.chromium.launch(
            headless=False,
            channel="msedge",
            slow_mo=50,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )
        # Remove the webdriver flag that bot detectors look for
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        print(f"Opening: {url}")
        print("Solve any CAPTCHA in the browser window...")
        print("(The browser will stay open until the page loads or timeout)")
        await page.goto(url, wait_until="commit")

        # Wait for real content to appear (CAPTCHA solved)
        selector = wait_for or "body"
        print(f"Waiting up to {timeout}s for '{selector}' to appear...")
        try:
            await page.wait_for_selector(
                selector, state="visible", timeout=timeout * 1000
            )
            print("Page loaded! Waiting for page to settle...")
            await page.wait_for_timeout(3000)
        except Exception:
            print(f"Timeout waiting for '{selector}' — exporting cookies anyway")
            try:
                await page.wait_for_timeout(1000)
            except Exception:
                pass

        # Export cookies
        cookies = await context.cookies()
        cookie_list = []
        for c in cookies:
            cookie_list.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "secure": c.get("secure", False),
                "httpOnly": c.get("httpOnly", False),
            })

        out_path = Path(output)
        out_path.write_text(json.dumps(cookie_list, indent=2), encoding="utf-8")
        print(f"\nExported {len(cookie_list)} cookies to {out_path}")

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export browser cookies after CAPTCHA")
    parser.add_argument("url", help="URL to open")
    parser.add_argument("--output", "-o", default="cookies.json", help="Output cookie file")
    parser.add_argument("--wait-for", default=None, help="CSS selector to wait for (real page content)")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds (default: 120)")
    args = parser.parse_args()

    asyncio.run(main(args.url, args.output, args.wait_for, args.timeout))
