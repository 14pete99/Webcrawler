"""JSON file CRUD for stealth profiles."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import get_settings
from ..models.stealth import StealthProfile


def _profiles_dir() -> Path:
    d = Path(get_settings().profiles_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_profiles() -> list[StealthProfile]:
    """Return all saved profiles."""
    profiles: list[StealthProfile] = []
    for f in _profiles_dir().glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        profiles.append(StealthProfile(**data))
    return profiles


def get_profile(profile_id: str) -> StealthProfile | None:
    """Load a single profile by id."""
    path = _profiles_dir() / f"{profile_id}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return StealthProfile(**data)


def save_profile(profile: StealthProfile) -> StealthProfile:
    """Create or update a profile."""
    path = _profiles_dir() / f"{profile.id}.json"
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


def delete_profile(profile_id: str) -> bool:
    """Delete a profile. Returns ``True`` if the file existed."""
    path = _profiles_dir() / f"{profile_id}.json"
    if path.is_file():
        path.unlink()
        return True
    return False
