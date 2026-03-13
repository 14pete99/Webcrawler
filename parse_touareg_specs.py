"""Parse Touareg specs from batch crawl results into structured JSON and CSV."""

import csv
import io
import json
import re
import sys
from pathlib import Path

SPEC_SECTIONS = [
    "Electrical", "Engine", "Transmission & Drivetrain", "Fuel",
    "Steering", "Wheels & Tyres", "Dimensions & Weights",
    "Warranty & Service", "Safety & Security",
]
STOP_SECTIONS = ["Other", "Probationary Plate Status"]


def extract_vehicle_name(md: str) -> str:
    m = re.search(r"#\s+(\d{4}\s+Volkswagen\s+Touareg[^\n]+)", md)
    return m.group(1).strip() if m else ""


def _flush_section(specs, section, kv_pairs):
    """Store accumulated key-value pairs into specs dict."""
    if section and kv_pairs:
        specs.setdefault(section, {})
        for j in range(0, len(kv_pairs) - 1, 2):
            specs[section][kv_pairs[j]] = kv_pairs[j + 1]


def extract_specs(md: str) -> dict[str, dict[str, str]]:
    lines = md.split("\n")

    # Find the start of the specs zone by looking for known spec-only fields
    # then scanning backwards to find the section header. These fields only
    # appear in the specifications section, not in features.
    spec_anchors = ("Number of Airbags", "Engine type", "Engine Size (cc)")
    spec_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in spec_anchors:
            # Walk back up to 10 lines to find the section header
            for j in range(i - 1, max(i - 10, 0), -1):
                clean = re.sub(r"\s*\u27e8\d+\u27e9\s*$", "", lines[j].strip()).strip()
                if clean in SPEC_SECTIONS:
                    spec_start = j
                    break
            break

    specs: dict[str, dict[str, str]] = {}
    current_section: str | None = None
    kv_pairs: list[str] = []

    for line in lines[spec_start:]:
        line = line.strip()
        if not line:
            continue
        clean = re.sub(r"\s*\u27e8\d+\u27e9\s*$", "", line).strip()

        if clean in SPEC_SECTIONS:
            _flush_section(specs, current_section, kv_pairs)
            current_section = clean
            kv_pairs = []
            continue

        if any(clean.startswith(s) for s in STOP_SECTIONS):
            _flush_section(specs, current_section, kv_pairs)
            current_section = None
            continue

        if clean.startswith("#"):
            _flush_section(specs, current_section, kv_pairs)
            current_section = None
            break

        if current_section:
            kv_pairs.append(clean)

    _flush_section(specs, current_section, kv_pairs)
    return specs


def main():
    combined = json.loads(
        Path("output/touareg-specs/combined.json").read_text(encoding="utf-8")
    )

    all_vehicles = []
    for entry in combined:
        url = entry["url"]
        md = entry.get("markdown", "")
        name = extract_vehicle_name(md)
        specs = extract_specs(md)

        flat: dict[str, str] = {"vehicle": name, "url": url}
        for section, kvs in specs.items():
            for key, val in kvs.items():
                flat_key = f"{section} | {key}"
                flat[flat_key] = val

        all_vehicles.append(flat)

    print(f"Parsed {len(all_vehicles)} vehicles")

    has_engine = sum(
        1 for v in all_vehicles
        if any("Engine" in k for k in v if k != "vehicle")
    )
    print(f"With engine specs: {has_engine}")

    # Save JSON
    out_dir = Path("output/touareg-specs")
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "all_specifications.json").write_text(
        json.dumps(all_vehicles, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Build CSV
    all_keys: set[str] = set()
    for v in all_vehicles:
        all_keys.update(v.keys())
    fieldnames = ["vehicle", "url"] + sorted(
        k for k in all_keys if k not in ("vehicle", "url")
    )

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for v in all_vehicles:
        writer.writerow(v)
    (out_dir / "all_specifications.csv").write_bytes(buf.getvalue().encode("utf-8"))

    print(f"Saved all_specifications.json and all_specifications.csv")
    print(f"CSV columns: {len(fieldnames)}")

    # Show sample
    sample = all_vehicles[0]
    print(f"\nSample: {sample['vehicle']}")
    for k, v in list(sample.items())[:20]:
        if k not in ("vehicle", "url"):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
