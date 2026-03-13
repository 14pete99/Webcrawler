"""Scrape all VW Touareg for-sale ads from carsales.com.au.

Uses Playwright with a real Edge browser to bypass DataDome bot protection.
The browser opens visually — solve any CAPTCHA once, then the script takes over
and crawls all search result pages + individual listing pages automatically.

All data (photos, specs, features, seller notes) is stored in a SQLite database
with a unique session ID and timestamps.

Usage:
    python scrape_touareg_ads.py [--output-dir ./output/touareg-ads]
                                 [--per-page-delay 3.0]
                                 [--resume]
"""

import argparse
import asyncio
import json
import logging
import random
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# --- Constants ---
SEARCH_URL = "https://www.carsales.com.au/cars/"
SEARCH_QUERY = "(C.Make.Volkswagen._.Model.Touareg.)"
RESULTS_PER_PAGE = 12
CARSALES_DOMAIN = "www.carsales.com.au"

DEFAULT_OUTPUT = Path("output/touareg-ads")
DB_NAME = "touareg_ads.db"


# ============================================================
# Phase 1: Discover listing URLs using Playwright
# ============================================================

async def discover_listing_urls(
    page,
    *,
    delay: float = 3.0,
    max_pages: int = 50,
) -> list[str]:
    """Paginate through carsales search results and extract all listing URLs."""
    all_urls: list[str] = []
    seen: set[str] = set()
    consecutive_empty = 0

    for page_num in range(max_pages):
        offset = page_num * RESULTS_PER_PAGE
        search_url = f"{SEARCH_URL}?q={SEARCH_QUERY}&offset={offset}"

        log.info("Discovering page %d (offset=%d)", page_num + 1, offset)

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            # Wait for listing cards to render
            try:
                await page.wait_for_selector(
                    'a[href*="/cars/details/"]',
                    state="attached",
                    timeout=10000,
                )
            except Exception:
                # Try waiting for general content
                await page.wait_for_timeout(3000)

            await page.wait_for_timeout(1500)

            # Scroll to load lazy content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

        except Exception as exc:
            log.error("Failed to load search page %d: %s", page_num + 1, exc)
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
            await asyncio.sleep(delay)
            continue

        # Extract listing URLs
        links = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/cars/details/"]');
            return [...new Set([...links].map(a => a.href.split('?')[0]))];
        }""")

        new_count = 0
        for url in links:
            if url not in seen and "/cars/details/" in url:
                seen.add(url)
                all_urls.append(url)
                new_count += 1

        log.info("  Found %d new listings (total: %d)", new_count, len(all_urls))

        if new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                log.info("No new listings on 2 consecutive pages — stopping discovery")
                break
        else:
            consecutive_empty = 0

        await asyncio.sleep(delay)

    log.info("Discovery complete: %d unique listing URLs", len(all_urls))
    return all_urls


# ============================================================
# Phase 2: Crawl individual listing page
# ============================================================

async def _human_delay(min_s: float = 1.0, max_s: float = 3.0):
    """Random delay to mimic human browsing."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _human_scroll(page):
    """Scroll page in a human-like way."""
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(300, 700)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.4, 1.2))


async def crawl_listing_page(
    page,
    url: str,
    *,
    delay: float = 2.0,
    max_retries: int = 2,
) -> dict | None:
    """Navigate to a listing page and extract all data."""
    for attempt in range(1, max_retries + 2):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait for main content
            try:
                await page.wait_for_selector("h1", state="visible", timeout=8000)
            except Exception:
                await page.wait_for_timeout(3000)

            await _human_delay(1.0, 2.5)

            # Scroll down to load lazy images and specs (human-like)
            await _human_scroll(page)

            # Extract everything from the page
            data = await page.evaluate("""() => {
                const result = {
                    url: window.location.href,
                    title: '',
                    html: document.documentElement.outerHTML,
                    photos: [],
                    jsonld: [],
                };

                // Title
                const h1 = document.querySelector('h1');
                if (h1) result.title = h1.innerText.trim();

                // JSON-LD structured data
                document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                    try { result.jsonld.push(JSON.parse(s.textContent)); } catch(e) {}
                });

                // All images (for photo extraction)
                const seen = new Set();
                document.querySelectorAll('img[src], img[data-src]').forEach(img => {
                    const src = img.src || img.dataset.src;
                    if (src && !seen.has(src) && src.startsWith('http')) {
                        seen.add(src);
                        result.photos.push({url: src, alt: img.alt || ''});
                    }
                });

                // Also get background images from gallery
                document.querySelectorAll('[style*="background-image"]').forEach(el => {
                    const m = el.style.backgroundImage.match(/url\\(['"]?(https[^'"\\)]+)/);
                    if (m && !seen.has(m[1])) {
                        seen.add(m[1]);
                        result.photos.push({url: m[1], alt: ''});
                    }
                });

                // Try to get all image URLs from gallery/carousel data attributes
                document.querySelectorAll('[data-image-url], [data-src]').forEach(el => {
                    const src = el.dataset.imageUrl || el.dataset.src;
                    if (src && !seen.has(src) && src.startsWith('http')) {
                        seen.add(src);
                        result.photos.push({url: src, alt: ''});
                    }
                });

                return result;
            }""")

            # Get clean text content for markdown-like parsing
            text_content = await page.evaluate("""() => {
                // Get all visible text in structured way
                const sections = [];

                // Key details section
                document.querySelectorAll('[class*="key-detail"], [class*="listing-detail"], [class*="overview"], [class*="specification"], [class*="feature"]').forEach(el => {
                    sections.push(el.innerText);
                });

                // Comments / seller notes
                document.querySelectorAll('[class*="comment"], [class*="description"], [class*="seller-note"]').forEach(el => {
                    sections.push('SELLER_NOTES: ' + el.innerText);
                });

                // General body text as fallback
                if (sections.length === 0) {
                    sections.push(document.body.innerText);
                }

                return sections.join('\\n---SECTION---\\n');
            }""")

            data["text_content"] = text_content
            return data

        except Exception as exc:
            log.warning("[attempt %d] %s — %s", attempt, url.split("/")[-2][:40], exc)
            if attempt <= max_retries:
                await asyncio.sleep(min(2 ** attempt, 10))

    return None


# ============================================================
# Phase 3: Parse extracted data into structured listing
# ============================================================

def parse_listing(data: dict) -> dict:
    """Parse raw page data into a structured listing dict."""
    url = data.get("url", "")
    html = data.get("html", "")
    text = data.get("text_content", "")
    raw_photos = data.get("photos", [])

    listing = {
        "url": url,
        "title": data.get("title", ""),
        "price": None,
        "price_text": "",
        "year": None,
        "make": "Volkswagen",
        "model": "Touareg",
        "variant": "",
        "badge": "",
        "body_type": "",
        "transmission": "",
        "fuel_type": "",
        "odometer_km": None,
        "colour": "",
        "drive_type": "",
        "doors": None,
        "seats": None,
        "rego": "",
        "rego_expiry": "",
        "vin": "",
        "stock_number": "",
        "location": "",
        "seller_name": "",
        "seller_type": "",
        "seller_notes": "",
        "features": [],
        "specs": {},
        "photos": [],
        "ad_id": "",
    }

    # --- Ad ID from URL ---
    ad_id_match = re.search(r"(OAG-AD-\w+|SSE-AD-\w+)", url)
    if ad_id_match:
        listing["ad_id"] = ad_id_match.group(1)

    # --- Year and variant from title ---
    year_match = re.search(r"\b(19|20)\d{2}\b", listing["title"])
    if year_match:
        listing["year"] = int(year_match.group(0))

    variant_match = re.match(r"\d{4}\s+Volkswagen\s+Touareg\s+(.*)", listing["title"])
    if variant_match:
        listing["variant"] = variant_match.group(1).strip()

    # --- JSON-LD structured data ---
    for jsonld in data.get("jsonld", []):
        _extract_jsonld(jsonld, listing)
        # Nested items (e.g., @graph)
        if isinstance(jsonld, dict) and "@graph" in jsonld:
            for item in jsonld["@graph"]:
                _extract_jsonld(item, listing)

    # --- Price from HTML ---
    price_patterns = [
        r'"price"[^:]*:\s*"?\$?([\d,]+)"?',
        r'class="[^"]*price[^"]*"[^>]*>\s*\$?([\d,]+)',
        r'\$\s*([\d,]+)\s*(?:Drive Away|EGC|Excl|plus|Inc)',
        r'data-price="([\d]+)"',
        r'"amount":\s*([\d]+)',
    ]
    for pattern in price_patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m and not listing["price"]:
            try:
                listing["price"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

    # Price from text
    if not listing["price"]:
        m = re.search(r"\$\s*([\d,]+)", text)
        if m:
            try:
                listing["price"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

    # Price text
    price_text_match = re.search(
        r'class="[^"]*price[^"]*"[^>]*>(.*?)</\w+>', html, re.DOTALL
    )
    if price_text_match:
        listing["price_text"] = re.sub(r"<[^>]+>", "", price_text_match.group(1)).strip()

    # --- Key-value details from text ---
    _extract_kv_from_text(text, listing)

    # --- Odometer ---
    if not listing["odometer_km"]:
        odo_patterns = [
            r"(\d[\d,]+)\s*km\b",
            r'[Oo]dometer[^:]*:\s*([\d,]+)',
        ]
        for pattern in odo_patterns:
            m = re.search(pattern, text + " " + html)
            if m:
                try:
                    val = int(m.group(1).replace(",", ""))
                    if val > 100:  # filter out small numbers that aren't odometers
                        listing["odometer_km"] = val
                        break
                except ValueError:
                    pass

    # --- Location from HTML ---
    loc_match = re.search(
        r'class="[^"]*location[^"]*"[^>]*>(.*?)</\w+>', html, re.DOTALL
    )
    if loc_match:
        listing["location"] = re.sub(r"<[^>]+>", "", loc_match.group(1)).strip()

    # Location from text
    if not listing["location"]:
        loc_text = re.search(r"(?:Location|Located)\s*:?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if loc_text:
            listing["location"] = loc_text.group(1).strip()

    # --- Seller ---
    seller_match = re.search(
        r'class="[^"]*dealer-name[^"]*"[^>]*>(.*?)</\w+>', html, re.DOTALL
    )
    if seller_match:
        listing["seller_name"] = re.sub(r"<[^>]+>", "", seller_match.group(1)).strip()
        listing["seller_type"] = "dealer"

    if not listing["seller_name"]:
        # Try text content
        dealer_text = re.search(r"(?:Dealer|Sold by|Seller)\s*:?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if dealer_text:
            listing["seller_name"] = dealer_text.group(1).strip()
            listing["seller_type"] = "dealer"

    if not listing["seller_type"]:
        if re.search(r"[Pp]rivate\s+[Ss]eller", text + html):
            listing["seller_type"] = "private"

    # --- Seller notes ---
    for section in text.split("---SECTION---"):
        if section.strip().startswith("SELLER_NOTES:"):
            notes = section.replace("SELLER_NOTES:", "").strip()
            if len(notes) > 10:
                listing["seller_notes"] = notes
                break

    if not listing["seller_notes"]:
        notes_patterns = [
            r'class="[^"]*(?:seller-?notes|comments|description)[^"]*"[^>]*>(.*?)</div>',
            r'class="[^"]*listing-description[^"]*"[^>]*>(.*?)</div>',
        ]
        for pattern in notes_patterns:
            m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if m:
                notes = re.sub(r"<[^>]+>", " ", m.group(1))
                notes = re.sub(r"\s+", " ", notes).strip()
                if len(notes) > 10:
                    listing["seller_notes"] = notes
                    break

    # --- Features ---
    features = set()
    feat_matches = re.findall(
        r'class="[^"]*feature[^"]*"[^>]*>(.*?)</(?:li|span|div)>',
        html, re.DOTALL | re.IGNORECASE,
    )
    for f in feat_matches:
        feat = re.sub(r"<[^>]+>", "", f).strip()
        if feat and 1 < len(feat) < 100:
            features.add(feat)

    # From text sections
    feat_section = re.search(
        r"(?:Key\s+)?Features?\s*\n((?:.*\n?)*?)(?=\n\n|\Z)",
        text, re.IGNORECASE,
    )
    if feat_section:
        for line in feat_section.group(1).splitlines():
            feat = line.strip().lstrip("-*• ")
            if feat and 1 < len(feat) < 100:
                features.add(feat)

    listing["features"] = sorted(features)

    # --- Specs from HTML tables and DL lists ---
    specs = {}
    spec_rows = re.findall(
        r"<tr[^>]*>\s*<t[dh][^>]*>(.*?)</t[dh]>\s*<t[dh][^>]*>(.*?)</t[dh]>",
        html, re.DOTALL,
    )
    for key_html, val_html in spec_rows:
        key = re.sub(r"<[^>]+>", "", key_html).strip()
        val = re.sub(r"<[^>]+>", "", val_html).strip()
        if key and val and len(key) < 80:
            specs[key] = val

    dt_dd = re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", html, re.DOTALL)
    for key_html, val_html in dt_dd:
        key = re.sub(r"<[^>]+>", "", key_html).strip()
        val = re.sub(r"<[^>]+>", "", val_html).strip()
        if key and val and len(key) < 80:
            specs[key] = val

    # From text key-value patterns
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Za-z\s&/().]+?)\s{2,}(.+)$", line.strip())
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            if key and val and len(key) < 80 and key not in specs:
                specs[key] = val

    listing["specs"] = specs

    # --- Photos ---
    photos = []
    seen_urls = set()
    for photo in raw_photos:
        src = photo.get("url", "")
        if src and src not in seen_urls and _is_vehicle_photo(src):
            seen_urls.add(src)
            photos.append(photo)

    # Also extract from HTML src patterns
    img_patterns = [
        r'"(https://[^"]*(?:carsales|csnstatic)[^"]*\.(?:jpg|jpeg|png|webp)[^"]*)"',
        r'data-src="(https://[^"]*\.(?:jpg|jpeg|png|webp)[^"]*)"',
    ]
    for pattern in img_patterns:
        for m in re.finditer(pattern, html, re.IGNORECASE):
            src = m.group(1)
            if src not in seen_urls and _is_vehicle_photo(src):
                seen_urls.add(src)
                photos.append({"url": src, "alt": ""})

    listing["photos"] = photos

    # --- Fill gaps from specs ---
    spec_field_map = {
        "colour": ["Colour", "Ext. Colour", "Exterior Colour", "Color"],
        "body_type": ["Body Style", "Body Type", "Body"],
        "transmission": ["Transmission", "Trans."],
        "fuel_type": ["Fuel Type", "FuelType", "Fuel"],
        "drive_type": ["Drive Type", "Drive", "Drivetrain"],
    }
    for field, keys in spec_field_map.items():
        if not listing[field]:
            for key in keys:
                if key in specs:
                    listing[field] = specs[key]
                    break

    return listing


def _is_vehicle_photo(url: str) -> bool:
    """Filter out non-vehicle images."""
    skip = [
        "logo", "icon", "badge", "sprite", "pixel", "tracking",
        "1x1", "spacer", "blank", "arrow", "button", "close",
        "favicon", "avatar", "star", "rating", "social",
        "facebook", "twitter", "instagram", "youtube",
        "google", "analytics", "doubleclick", "adsense",
        "svg", ".gif",
    ]
    url_lower = url.lower()
    return not any(s in url_lower for s in skip) and len(url) > 30


def _extract_jsonld(jsonld: dict, listing: dict):
    """Extract data from JSON-LD structured data."""
    if not isinstance(jsonld, dict):
        return
    item_type = jsonld.get("@type", "")
    if isinstance(item_type, list):
        item_type = item_type[0] if item_type else ""
    if item_type not in ("Car", "Vehicle", "Product", "Offer", "AutoDealer"):
        return

    if not listing["title"] and jsonld.get("name"):
        listing["title"] = str(jsonld["name"])
    if not listing["price"]:
        offers = jsonld.get("offers", jsonld)
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if isinstance(offers, dict):
            price = offers.get("price") or offers.get("lowPrice")
            if price:
                try:
                    listing["price"] = int(float(str(price).replace(",", "")))
                except (ValueError, TypeError):
                    pass
    for src_key, dst_key in [
        ("color", "colour"), ("vehicleTransmission", "transmission"),
        ("fuelType", "fuel_type"), ("bodyType", "body_type"),
        ("vehicleIdentificationNumber", "vin"),
    ]:
        if jsonld.get(src_key) and not listing.get(dst_key):
            listing[dst_key] = str(jsonld[src_key])

    if jsonld.get("mileageFromOdometer") and not listing["odometer_km"]:
        odo = jsonld["mileageFromOdometer"]
        val = odo.get("value") if isinstance(odo, dict) else odo
        if val:
            try:
                listing["odometer_km"] = int(float(str(val).replace(",", "")))
            except (ValueError, TypeError):
                pass

    # Seller info from AutoDealer
    if item_type == "AutoDealer" and not listing["seller_name"]:
        listing["seller_name"] = str(jsonld.get("name", ""))
        listing["seller_type"] = "dealer"
        if jsonld.get("address"):
            addr = jsonld["address"]
            if isinstance(addr, dict):
                parts = [addr.get("addressLocality", ""), addr.get("addressRegion", "")]
                listing["location"] = ", ".join(p for p in parts if p)


def _extract_kv_from_text(text: str, listing: dict):
    """Extract key-value pairs from visible text content."""
    field_map = {
        "Badge": "badge",
        "Body Style": "body_type",
        "Body Type": "body_type",
        "Body": "body_type",
        "Transmission": "transmission",
        "Drive Type": "drive_type",
        "Drive": "drive_type",
        "Drivetrain": "drive_type",
        "Fuel Type": "fuel_type",
        "FuelType": "fuel_type",
        "Colour": "colour",
        "Ext. Colour": "colour",
        "Exterior Colour": "colour",
        "No. Doors": "doors",
        "Doors": "doors",
        "Seat Capacity": "seats",
        "Seats": "seats",
        "Registration": "rego",
        "Rego": "rego",
        "Registration Expiry": "rego_expiry",
        "Stock No.": "stock_number",
        "Stock Number": "stock_number",
        "VIN": "vin",
    }

    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in field_map and i + 1 < len(lines):
            value = lines[i + 1].strip()
            if value and not value.startswith("#"):
                db_field = field_map[stripped]
                if not listing.get(db_field):
                    if db_field in ("doors", "seats"):
                        try:
                            listing[db_field] = int(value)
                        except ValueError:
                            pass
                    else:
                        listing[db_field] = value


# ============================================================
# Phase 4: SQLite Database
# ============================================================

def create_schema(conn: sqlite3.Connection):
    """Create the database schema for scraped ads."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scrape_sessions (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            total_urls_discovered INTEGER DEFAULT 0,
            total_listings_scraped INTEGER DEFAULT 0,
            total_photos_found INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',
            search_url TEXT
        );

        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES scrape_sessions(id),
            ad_id TEXT,
            url TEXT NOT NULL,
            title TEXT,
            price INTEGER,
            price_text TEXT,
            year INTEGER,
            make TEXT DEFAULT 'Volkswagen',
            model TEXT DEFAULT 'Touareg',
            variant TEXT,
            badge TEXT,
            body_type TEXT,
            transmission TEXT,
            fuel_type TEXT,
            odometer_km INTEGER,
            colour TEXT,
            drive_type TEXT,
            doors INTEGER,
            seats INTEGER,
            rego TEXT,
            rego_expiry TEXT,
            vin TEXT,
            stock_number TEXT,
            location TEXT,
            seller_name TEXT,
            seller_type TEXT,
            seller_notes TEXT,
            scraped_at TEXT NOT NULL,
            UNIQUE(session_id, url)
        );

        CREATE TABLE IF NOT EXISTS listing_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL REFERENCES listings(id),
            url TEXT NOT NULL,
            alt TEXT,
            position INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS listing_specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL REFERENCES listings(id),
            key TEXT NOT NULL,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS listing_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL REFERENCES listings(id),
            feature TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_listings_session ON listings(session_id);
        CREATE INDEX IF NOT EXISTS idx_listings_year ON listings(year);
        CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
        CREATE INDEX IF NOT EXISTS idx_listings_ad_id ON listings(ad_id);
        CREATE INDEX IF NOT EXISTS idx_photos_listing ON listing_photos(listing_id);
        CREATE INDEX IF NOT EXISTS idx_specs_listing ON listing_specs(listing_id);
        CREATE INDEX IF NOT EXISTS idx_features_listing ON listing_features(listing_id);

        CREATE VIEW IF NOT EXISTS listing_summary AS
        SELECT
            l.id,
            l.session_id,
            l.ad_id,
            l.title,
            l.price,
            l.year,
            l.variant,
            l.badge,
            l.body_type,
            l.transmission,
            l.fuel_type,
            l.odometer_km,
            l.colour,
            l.drive_type,
            l.location,
            l.seller_type,
            (SELECT COUNT(*) FROM listing_photos p WHERE p.listing_id = l.id) AS photo_count,
            (SELECT COUNT(*) FROM listing_specs s WHERE s.listing_id = l.id) AS spec_count,
            (SELECT COUNT(*) FROM listing_features f WHERE f.listing_id = l.id) AS feature_count,
            l.scraped_at
        FROM listings l;
    """)


def store_listing(conn: sqlite3.Connection, session_id: str, listing: dict) -> int | None:
    """Insert a parsed listing into the database. Returns listing_id."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            """INSERT INTO listings
               (session_id, ad_id, url, title, price, price_text, year, make, model,
                variant, badge, body_type, transmission, fuel_type, odometer_km,
                colour, drive_type, doors, seats, rego, rego_expiry, vin,
                stock_number, location, seller_name, seller_type, seller_notes,
                scraped_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, listing["ad_id"], listing["url"], listing["title"],
                listing["price"], listing["price_text"], listing["year"],
                listing["make"], listing["model"], listing["variant"],
                listing["badge"], listing["body_type"], listing["transmission"],
                listing["fuel_type"], listing["odometer_km"], listing["colour"],
                listing["drive_type"], listing["doors"], listing["seats"],
                listing["rego"], listing["rego_expiry"], listing["vin"],
                listing["stock_number"], listing["location"], listing["seller_name"],
                listing["seller_type"], listing["seller_notes"], now,
            ),
        )
    except sqlite3.IntegrityError:
        log.warning("Duplicate listing skipped: %s", listing["url"])
        return None

    listing_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    for i, photo in enumerate(listing.get("photos", [])):
        conn.execute(
            "INSERT INTO listing_photos (listing_id, url, alt, position) VALUES (?,?,?,?)",
            (listing_id, photo["url"], photo.get("alt", ""), i),
        )

    for key, value in listing.get("specs", {}).items():
        conn.execute(
            "INSERT INTO listing_specs (listing_id, key, value) VALUES (?,?,?)",
            (listing_id, key, value),
        )

    for feature in listing.get("features", []):
        conn.execute(
            "INSERT INTO listing_features (listing_id, feature) VALUES (?,?)",
            (listing_id, feature),
        )

    return listing_id


def get_incomplete_session(conn: sqlite3.Connection) -> tuple[str, list[str]] | None:
    """Check for an incomplete session to resume."""
    row = conn.execute(
        "SELECT id FROM scrape_sessions WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    session_id = row[0]
    scraped = [r[0] for r in conn.execute(
        "SELECT url FROM listings WHERE session_id = ?", (session_id,)
    ).fetchall()]
    return session_id, scraped


# ============================================================
# Main orchestrator
# ============================================================

async def run(args):
    from playwright.async_api import async_playwright

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / DB_NAME

    # Database setup
    conn = sqlite3.connect(str(db_path))
    create_schema(conn)

    # Check for resume
    session_id = None
    already_scraped: set[str] = set()

    if args.resume:
        result = get_incomplete_session(conn)
        if result:
            session_id, scraped_urls = result
            already_scraped = set(scraped_urls)
            log.info("Resuming session %s (%d already scraped)", session_id, len(already_scraped))

    if not session_id:
        session_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO scrape_sessions (id, started_at, status, search_url) VALUES (?,?,?,?)",
            (session_id, datetime.now(timezone.utc).isoformat(), "running",
             f"{SEARCH_URL}?q={SEARCH_QUERY}"),
        )
        conn.commit()

    log.info("Scrape session: %s", session_id)
    delay = args.per_page_delay

    async with async_playwright() as p:
        # Use persistent context with Edge — this uses a real browser profile
        # on disk so cookies/sessions persist across runs, making it look like
        # a real returning user rather than a fresh automation session.
        profile_dir = output_dir / ".browser-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            channel="msedge",
            slow_mo=100,  # subtle slowdown to appear human
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            viewport={"width": 1366, "height": 768},  # common laptop resolution
            locale="en-AU",
            timezone_id="Australia/Sydney",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // Spoof plugins to look like real Edge
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            // Remove automation indicators
            delete window.__playwright;
            delete window.__pw_manual;
        """)

        # --- Navigate to first search page and wait for CAPTCHA ---
        log.info("=" * 60)
        log.info("Opening carsales.com.au — solve any CAPTCHA in the browser window")
        log.info("=" * 60)

        first_url = f"{SEARCH_URL}?q={SEARCH_QUERY}&offset=0"
        await page.goto(first_url, wait_until="commit")

        # Wait for real content (user solves CAPTCHA)
        print("\n>>> A browser window has opened.")
        print(">>> If you see a CAPTCHA, solve it manually.")
        print(">>> The script will continue automatically once the page loads.\n")

        try:
            await page.wait_for_selector(
                'a[href*="/cars/details/"]',
                state="attached",
                timeout=180000,  # 3 minutes to solve CAPTCHA
            )
            log.info("Page loaded — CAPTCHA passed!")
        except Exception:
            # Check if we got past the CAPTCHA at all
            try:
                content = await page.content()
            except Exception:
                log.error("Browser was closed. Please run the script again.")
                conn.close()
                return
            if "captcha" in content.lower() or "datadome" in content.lower():
                log.error("CAPTCHA not solved within timeout. Please try again.")
                await context.close()
                conn.close()
                return
            log.info("Page loaded (no listing links found on first try, continuing...)")

        await page.wait_for_timeout(2000)

        # ===== Phase 1: Discover listing URLs =====
        urls_file = output_dir / "listing_urls.json"
        if urls_file.exists() and args.resume:
            listing_urls = json.loads(urls_file.read_text(encoding="utf-8"))
            log.info("Loaded %d URLs from previous discovery", len(listing_urls))
        else:
            log.info("=" * 60)
            log.info("PHASE 1: Discovering listing URLs")
            log.info("=" * 60)

            # Extract from the page we already loaded
            initial_links = await page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/cars/details/"]');
                return [...new Set([...links].map(a => a.href.split('?')[0]))];
            }""")

            listing_urls = list(dict.fromkeys(initial_links))  # dedupe preserving order
            log.info("  Page 1: found %d listings", len(listing_urls))

            # Continue paginating
            listing_urls = await _paginate_remaining(
                page, listing_urls, delay=delay
            )

            urls_file.write_text(
                json.dumps(listing_urls, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        conn.execute(
            "UPDATE scrape_sessions SET total_urls_discovered = ? WHERE id = ?",
            (len(listing_urls), session_id),
        )
        conn.commit()

        # Filter already scraped
        urls_to_crawl = [u for u in listing_urls if u not in already_scraped]
        log.info("Total URLs: %d | To crawl: %d | Already done: %d",
                 len(listing_urls), len(urls_to_crawl), len(already_scraped))

        if not urls_to_crawl:
            log.info("All URLs already scraped!")
            _print_summary(conn, session_id)
            await context.close()
            conn.close()
            return

        # ===== Phase 2 & 3: Crawl + Parse + Store =====
        log.info("=" * 60)
        log.info("PHASE 2: Crawling %d listings", len(urls_to_crawl))
        log.info("=" * 60)

        scraped_count = len(already_scraped)
        total_photos = 0
        failed = 0

        for i, url in enumerate(urls_to_crawl):
            log.info("[%d/%d] Crawling: %s",
                     i + 1, len(urls_to_crawl),
                     url.split("/")[-2][:50] if "/" in url else url[:60])

            raw_data = await crawl_listing_page(page, url, delay=delay)

            if raw_data:
                listing = parse_listing(raw_data)
                listing_id = store_listing(conn, session_id, listing)
                if listing_id:
                    scraped_count += 1
                    n_photos = len(listing.get("photos", []))
                    total_photos += n_photos
                    log.info("  -> %s | $%s | %s km | %d photos | %d specs",
                             listing.get("title", "?")[:50],
                             f"{listing['price']:,}" if listing["price"] else "?",
                             f"{listing['odometer_km']:,}" if listing["odometer_km"] else "?",
                             n_photos,
                             len(listing.get("specs", {})))
                else:
                    log.info("  -> (duplicate, skipped)")
            else:
                failed += 1
                log.warning("  -> FAILED")

            # Periodic commit + progress
            if (i + 1) % 10 == 0:
                conn.commit()
                log.info("--- Progress: %d/%d scraped, %d failed ---",
                         scraped_count - len(already_scraped), len(urls_to_crawl), failed)

            # Human-like variable delay (some faster, some slower)
            await _human_delay(delay * 0.7, delay * 1.8)

        # Final update
        conn.execute(
            """UPDATE scrape_sessions SET
                 completed_at = ?,
                 total_listings_scraped = ?,
                 total_photos_found = ?,
                 status = 'completed'
               WHERE id = ?""",
            (datetime.now(timezone.utc).isoformat(), scraped_count, total_photos, session_id),
        )
        conn.commit()

        await context.close()

    _print_summary(conn, session_id)
    conn.close()

    log.info("Database saved: %s", db_path)
    log.info("Session ID: %s", session_id)


async def _paginate_remaining(page, initial_urls: list[str], *, delay: float) -> list[str]:
    """Continue paginating search results after page 1."""
    all_urls = list(initial_urls)
    seen = set(all_urls)
    consecutive_empty = 0

    for page_num in range(1, 50):  # pages 2-50
        offset = page_num * RESULTS_PER_PAGE
        search_url = f"{SEARCH_URL}?q={SEARCH_QUERY}&offset={offset}"

        log.info("  Discovering page %d (offset=%d)", page_num + 1, offset)

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(
                    'a[href*="/cars/details/"]', state="attached", timeout=10000
                )
            except Exception:
                await page.wait_for_timeout(3000)

            await _human_delay(1.5, 3.0)

            # Scroll to load lazy content (human-like)
            await _human_scroll(page)

        except Exception as exc:
            log.warning("  Page %d failed: %s", page_num + 1, exc)
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
            await _human_delay(delay, delay + 3)
            continue

        links = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/cars/details/"]');
            return [...new Set([...links].map(a => a.href.split('?')[0]))];
        }""")

        new_count = 0
        for url in links:
            if url not in seen and "/cars/details/" in url:
                seen.add(url)
                all_urls.append(url)
                new_count += 1

        log.info("    Found %d new (total: %d)", new_count, len(all_urls))

        if new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                log.info("  No new listings for 2 pages — discovery complete")
                break
        else:
            consecutive_empty = 0

        # Human-like variable delay between pages
        await _human_delay(delay, delay + 4)

    return all_urls


def _print_summary(conn: sqlite3.Connection, session_id: str):
    """Print a summary of the scrape results."""
    print("\n" + "=" * 60)
    print("SCRAPE SUMMARY")
    print("=" * 60)

    row = conn.execute(
        "SELECT total_urls_discovered, total_listings_scraped, total_photos_found, "
        "started_at, completed_at FROM scrape_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if row:
        print(f"  Session ID:      {session_id}")
        print(f"  URLs discovered: {row[0]}")
        print(f"  Listings stored: {row[1]}")
        print(f"  Photos found:    {row[2]}")
        print(f"  Started:         {row[3]}")
        print(f"  Completed:       {row[4] or 'in progress'}")

    price_row = conn.execute(
        "SELECT COUNT(*), MIN(price), MAX(price), AVG(price) "
        "FROM listings WHERE session_id = ? AND price IS NOT NULL",
        (session_id,),
    ).fetchone()
    if price_row and price_row[0]:
        print(f"\n  Listings with price: {price_row[0]}")
        print(f"  Price range: ${price_row[1]:,} - ${price_row[2]:,}")
        print(f"  Average price: ${int(price_row[3]):,}")

    print("\n  Year distribution:")
    for row in conn.execute(
        "SELECT year, COUNT(*) FROM listings WHERE session_id = ? AND year IS NOT NULL "
        "GROUP BY year ORDER BY year DESC LIMIT 10",
        (session_id,),
    ):
        print(f"    {row[0]}: {row[1]} listings")

    print("\n  Seller types:")
    for row in conn.execute(
        "SELECT COALESCE(seller_type, 'unknown'), COUNT(*) FROM listings "
        "WHERE session_id = ? GROUP BY seller_type",
        (session_id,),
    ):
        print(f"    {row[0]}: {row[1]}")

    photo_row = conn.execute(
        "SELECT COUNT(*), AVG(cnt) FROM "
        "(SELECT COUNT(*) as cnt FROM listing_photos p "
        " JOIN listings l ON l.id = p.listing_id "
        " WHERE l.session_id = ? GROUP BY p.listing_id)",
        (session_id,),
    ).fetchone()
    if photo_row and photo_row[0]:
        print(f"\n  Listings with photos: {photo_row[0]}")
        print(f"  Avg photos/listing:  {photo_row[1]:.1f}")

    spec_row = conn.execute(
        "SELECT COUNT(*), AVG(cnt) FROM "
        "(SELECT COUNT(*) as cnt FROM listing_specs s "
        " JOIN listings l ON l.id = s.listing_id "
        " WHERE l.session_id = ? GROUP BY s.listing_id)",
        (session_id,),
    ).fetchone()
    if spec_row and spec_row[0]:
        print(f"  Listings with specs: {spec_row[0]}")
        print(f"  Avg specs/listing:   {spec_row[1]:.1f}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape all VW Touareg ads from carsales.com.au"
    )
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUTPUT),
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--per-page-delay", type=float, default=5.0,
        help="Base seconds between page loads (default: 5.0, randomized ±40%%)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from last incomplete session",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
