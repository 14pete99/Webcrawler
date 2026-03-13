"""Build a SQLite database from Touareg batch crawl results.

Creates a normalized database with:
- vehicles: core identity (year, variant, badge, series, price)
- specs: key-value spec data per vehicle (section, key, value, numeric_value)

Usage:
    python build_touareg_db.py
"""

import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path("output/touareg-specs/touareg.db")
COMBINED_PATH = Path("output/touareg-specs/combined.json")
SPECS_PATH = Path("output/touareg-specs/all_specifications.json")

# Spec sections to ingest
SPEC_SECTIONS = [
    "Electrical", "Engine", "Transmission & Drivetrain", "Fuel",
    "Steering", "Wheels & Tyres", "Dimensions & Weights",
    "Warranty & Service", "Safety & Security",
]

# Overview fields to extract from markdown (key in markdown -> DB column)
OVERVIEW_FIELDS = {
    "Badge": "badge",
    "Series": "series",
    "Body": "body_type",
    "No. Doors": "doors",
    "Seat Capacity": "seats",
    "Transmission": "transmission",
    "Drive": "drive_type",
    "FuelType": "fuel_type",
    "Recommended RON Rating": "ron_rating",
    "Release Date": "release_date",
    "Country of Origin": "country_of_origin",
}


def parse_vehicle_name(name: str) -> dict:
    """Extract year and variant from vehicle name."""
    m = re.match(r"(\d{4})\s+Volkswagen\s+Touareg\s+(.*)", name)
    if m:
        return {"year": int(m.group(1)), "variant": m.group(2).strip()}
    return {"year": 0, "variant": name}


def extract_overview(md: str) -> dict:
    """Extract overview key-value pairs from markdown (before spec sections)."""
    overview = {}
    lines = md.split("\n")

    # Find "Price When New" value — two formats:
    #   1. "Price When New  139,990*" (inline on same line)
    #   2. "Price When New\n$139,990" (label + next line)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "Price When New" in stripped and "Price Guide" not in stripped:
            # Try inline: "Price When New  133,490*"
            m = re.search(r"Price When New\s+\$?([\d,]+)", stripped)
            if m:
                overview["price_when_new"] = int(m.group(1).replace(",", ""))
                break
            # Try next line
            if stripped == "Price When New" and i + 1 < len(lines):
                price_line = lines[i + 1].strip()
                m = re.search(r"\$?([\d,]+)", price_line)
                if m:
                    overview["price_when_new"] = int(m.group(1).replace(",", ""))
                    break

    # Extract overview fields from the details section.
    # After "Overview ^", fields follow "key\nvalue" pattern.
    # Find the overview section start.
    overview_start = 0
    for i, line in enumerate(lines):
        if "Overview" in line and "^" in line:
            overview_start = i
            break

    for i, line in enumerate(lines[overview_start:], start=overview_start):
        stripped = line.strip()
        if stripped in OVERVIEW_FIELDS and i + 1 < len(lines):
            value = lines[i + 1].strip()
            if value and not value.startswith("#") and not value.startswith("*"):
                db_col = OVERVIEW_FIELDS[stripped]
                overview[db_col] = value

    return overview


def extract_numeric(value: str) -> float | None:
    """Try to extract a numeric value from a spec string."""
    if not value:
        return None
    # Remove units and extract number: "162.0 kW" -> 162.0, "3189 cc" -> 3189
    m = re.match(r"^([\d,.]+)", value.strip())
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def create_schema(conn: sqlite3.Connection):
    conn.executescript("""
        DROP VIEW IF EXISTS vehicle_summary;
        DROP TABLE IF EXISTS specs;
        DROP TABLE IF EXISTS vehicles;

        CREATE TABLE vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            variant TEXT NOT NULL,
            vehicle_name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            badge TEXT,
            series TEXT,
            body_type TEXT,
            doors INTEGER,
            seats INTEGER,
            transmission TEXT,
            drive_type TEXT,
            fuel_type TEXT,
            ron_rating TEXT,
            release_date TEXT,
            country_of_origin TEXT,
            price_when_new INTEGER
        );

        CREATE TABLE specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            section TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            numeric_value REAL,
            unit TEXT
        );

        CREATE INDEX idx_specs_vehicle ON specs(vehicle_id);
        CREATE INDEX idx_specs_section ON specs(section);
        CREATE INDEX idx_specs_key ON specs(key);
        CREATE INDEX idx_vehicles_year ON vehicles(year);

        -- Handy view: one row per vehicle with key specs pivoted
        CREATE VIEW vehicle_summary AS
        SELECT
            v.id,
            v.year,
            v.variant,
            v.vehicle_name,
            v.badge,
            v.series,
            v.price_when_new,
            v.fuel_type,
            v.drive_type,
            MAX(CASE WHEN s.section='Engine' AND s.key='Power' THEN s.value END) AS power,
            MAX(CASE WHEN s.section='Engine' AND s.key='Power' THEN s.numeric_value END) AS power_kw,
            MAX(CASE WHEN s.section='Engine' AND s.key='Torque' THEN s.value END) AS torque,
            MAX(CASE WHEN s.section='Engine' AND s.key='Torque' THEN s.numeric_value END) AS torque_nm,
            MAX(CASE WHEN s.section='Engine' AND s.key='Engine Size (L)' THEN s.value END) AS engine_size,
            MAX(CASE WHEN s.section='Engine' AND s.key='Cylinders' THEN s.value END) AS cylinders,
            MAX(CASE WHEN s.section='Engine' AND s.key='Acceleration 0-100km/h' THEN s.value END) AS accel_0_100,
            MAX(CASE WHEN s.section='Engine' AND s.key='Acceleration 0-100km/h' THEN s.numeric_value END) AS accel_0_100_s,
            MAX(CASE WHEN s.section='Fuel' AND s.key='Fuel Consumption Combined ‡' THEN s.value END) AS fuel_combined,
            MAX(CASE WHEN s.section='Fuel' AND s.key='Fuel Consumption Combined ‡' THEN s.numeric_value END) AS fuel_combined_lper100,
            MAX(CASE WHEN s.section='Fuel' AND s.key='CO2 Emission Combined' THEN s.value END) AS co2_combined,
            MAX(CASE WHEN s.section='Dimensions & Weights' AND s.key='Kerb Weight' THEN s.value END) AS kerb_weight,
            MAX(CASE WHEN s.section='Dimensions & Weights' AND s.key='Kerb Weight' THEN s.numeric_value END) AS kerb_weight_kg,
            MAX(CASE WHEN s.section='Dimensions & Weights' AND s.key='Length' THEN s.numeric_value END) AS length_mm,
            MAX(CASE WHEN s.section='Dimensions & Weights' AND s.key='Towing Capacity (braked)' THEN s.numeric_value END) AS towing_braked_kg,
            MAX(CASE WHEN s.section='Transmission & Drivetrain' AND s.key='Gears' THEN s.value END) AS gears,
            MAX(CASE WHEN s.section='Electrical' AND s.key='High Voltage Battery Capacity' THEN s.value END) AS battery_capacity,
            MAX(CASE WHEN s.section='Electrical' AND s.key='Electric Driving Range km (WLTP)' THEN s.value END) AS ev_range_wltp,
            MAX(CASE WHEN s.section='Wheels & Tyres' AND s.key='Front Tyre Description' THEN s.value END) AS front_tyres,
            MAX(CASE WHEN s.section='Safety & Security' AND s.key='ANCAP Rating' THEN s.value END) AS ancap_rating
        FROM vehicles v
        LEFT JOIN specs s ON s.vehicle_id = v.id
        GROUP BY v.id;
    """)


def extract_unit(value: str) -> str | None:
    """Extract unit from a spec value string."""
    m = re.match(r"^[\d,.]+\s*(.+)$", value.strip())
    if m:
        unit = m.group(1).strip()
        return unit if unit else None
    return None


def main():
    combined = json.loads(COMBINED_PATH.read_text(encoding="utf-8"))
    specs_data = json.loads(SPECS_PATH.read_text(encoding="utf-8"))

    # Build URL -> specs mapping
    url_to_specs = {}
    for entry in specs_data:
        url_to_specs[entry["url"]] = entry

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    create_schema(conn)

    vehicle_count = 0
    spec_count = 0

    for entry in combined:
        url = entry["url"]
        md = entry.get("markdown", "")

        # Vehicle name
        spec_entry = url_to_specs.get(url, {})
        vehicle_name = spec_entry.get("vehicle", "")
        if not vehicle_name:
            # Try extracting from markdown
            m = re.search(r"#\s+(\d{4}\s+Volkswagen\s+Touareg[^\n]+)", md)
            vehicle_name = m.group(1).strip() if m else url.split("/")[-2]

        parsed = parse_vehicle_name(vehicle_name)
        overview = extract_overview(md)

        # Insert vehicle
        conn.execute(
            """INSERT INTO vehicles
               (year, variant, vehicle_name, url, badge, series, body_type,
                doors, seats, transmission, drive_type, fuel_type,
                ron_rating, release_date, country_of_origin, price_when_new)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                parsed["year"],
                parsed["variant"],
                vehicle_name,
                url,
                overview.get("badge"),
                overview.get("series"),
                overview.get("body_type"),
                int(overview["doors"]) if overview.get("doors", "").isdigit() else None,
                int(overview["seats"]) if overview.get("seats", "").isdigit() else None,
                overview.get("transmission"),
                overview.get("drive_type"),
                overview.get("fuel_type"),
                overview.get("ron_rating"),
                overview.get("release_date"),
                overview.get("country_of_origin"),
                overview.get("price_when_new"),
            ),
        )
        vehicle_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        vehicle_count += 1

        # Insert specs
        for col_key, value in spec_entry.items():
            if " | " not in col_key:
                continue
            section, key = col_key.split(" | ", 1)
            numeric = extract_numeric(value)
            unit = extract_unit(value)
            conn.execute(
                """INSERT INTO specs (vehicle_id, section, key, value, numeric_value, unit)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (vehicle_id, section, key, value, numeric, unit),
            )
            spec_count += 1

    conn.commit()

    # Print summary
    print(f"Database: {DB_PATH}")
    print(f"Vehicles: {vehicle_count}")
    print(f"Spec rows: {spec_count}")

    # Run some sample queries
    print("\n--- Year range ---")
    row = conn.execute("SELECT MIN(year), MAX(year) FROM vehicles").fetchone()
    print(f"  {row[0]} - {row[1]}")

    print("\n--- Vehicles per decade ---")
    for row in conn.execute(
        "SELECT (year/10)*10 AS decade, COUNT(*) FROM vehicles GROUP BY decade ORDER BY decade"
    ):
        print(f"  {row[0]}s: {row[1]}")

    print("\n--- Top 5 most powerful ---")
    for row in conn.execute(
        """SELECT v.vehicle_name, s.value
           FROM specs s JOIN vehicles v ON v.id = s.vehicle_id
           WHERE s.key = 'Power' AND s.section = 'Engine'
           ORDER BY s.numeric_value DESC LIMIT 5"""
    ):
        print(f"  {row[0]}: {row[1]}")

    print("\n--- Fastest 0-100 ---")
    for row in conn.execute(
        """SELECT v.vehicle_name, s.value
           FROM specs s JOIN vehicles v ON v.id = s.vehicle_id
           WHERE s.key = 'Acceleration 0-100km/h'
           ORDER BY s.numeric_value ASC LIMIT 5"""
    ):
        print(f"  {row[0]}: {row[1]}")

    print("\n--- Price evolution (cheapest per year) ---")
    for row in conn.execute(
        """SELECT year, MIN(price_when_new), vehicle_name
           FROM vehicles WHERE price_when_new IS NOT NULL
           GROUP BY year ORDER BY year"""
    ):
        print(f"  {row[0]}: ${row[1]:,} ({row[2]})")

    print("\n--- Vehicle summary view sample ---")
    for row in conn.execute(
        "SELECT vehicle_name, power, accel_0_100, fuel_combined, kerb_weight FROM vehicle_summary ORDER BY year DESC LIMIT 5"
    ):
        print(f"  {row[0]}: {row[1]}, {row[2]}, {row[3]}, {row[4]}")

    conn.close()


if __name__ == "__main__":
    main()
