"""
Validate FEATURES.json: ensure all critical files exist and the manifest is well-formed.

Usage:
    python scripts/validate-features.py [--quiet]

Exit codes:
    0 — all checks pass
    1 — validation errors found
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES_FILE = REPO_ROOT / "FEATURES.json"

REQUIRED_FEATURE_KEYS = {"id", "name", "critical_files"}


def load_features() -> dict:
    if not FEATURES_FILE.exists():
        raise FileNotFoundError(f"FEATURES.json not found at {FEATURES_FILE}")
    with open(FEATURES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def validate(quiet: bool = False) -> list[str]:
    errors: list[str] = []

    try:
        data = load_features()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return [str(e)]

    if "features" not in data:
        return ["FEATURES.json missing top-level 'features' array"]

    features = data["features"]
    if not isinstance(features, list):
        return ["'features' must be an array"]

    seen_ids: set[str] = set()

    for i, feature in enumerate(features):
        prefix = f"features[{i}]"

        # Check required keys
        missing = REQUIRED_FEATURE_KEYS - set(feature.keys())
        if missing:
            errors.append(f"{prefix}: missing required keys: {', '.join(sorted(missing))}")
            continue

        fid = feature["id"]

        # Check duplicate IDs
        if fid in seen_ids:
            errors.append(f"{prefix}: duplicate feature id '{fid}'")
        seen_ids.add(fid)

        # Check critical files exist
        critical_files = feature.get("critical_files", [])
        if not isinstance(critical_files, list):
            errors.append(f"{prefix} ({fid}): 'critical_files' must be an array")
            continue

        for filepath in critical_files:
            full_path = REPO_ROOT / filepath
            if not full_path.exists():
                errors.append(f"{prefix} ({fid}): critical file missing: {filepath}")

        # Check api_endpoints is a list if present
        endpoints = feature.get("api_endpoints")
        if endpoints is not None and not isinstance(endpoints, list):
            errors.append(f"{prefix} ({fid}): 'api_endpoints' must be an array")

    if not quiet and not errors:
        print(f"FEATURES.json: {len(features)} feature(s) validated, all OK")
    elif not quiet and errors:
        print(f"FEATURES.json: {len(errors)} error(s) found:")
        for err in errors:
            print(f"  - {err}")

    return errors


def main():
    quiet = "--quiet" in sys.argv
    errors = validate(quiet)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
