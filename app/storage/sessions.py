"""Cookie jar persistence per session."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import get_settings
from ..models.session import SessionInfo


def _sessions_dir() -> Path:
    d = Path(get_settings().sessions_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_sessions() -> list[SessionInfo]:
    """Return metadata for all persisted sessions."""
    sessions: list[SessionInfo] = []
    for f in _sessions_dir().glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        cookies = data.get("cookies", [])
        local_storage = data.get("local_storage", {})
        sessions.append(
            SessionInfo(
                id=f.stem,
                has_cookies=bool(cookies),
                cookie_count=len(cookies),
                has_local_storage=bool(local_storage),
                fingerprint_seed=data.get("fingerprint_seed"),
            )
        )
    return sessions


def get_session_cookies(session_id: str) -> list[dict] | None:
    """Load cookies for a session."""
    profile = get_session_profile(session_id)
    if profile is None:
        return None
    return profile.get("cookies", [])


def save_session_cookies(session_id: str, cookies: list[dict]) -> None:
    """Persist cookies for a session (backward compat wrapper)."""
    existing = get_session_profile(session_id) or {}
    existing["cookies"] = cookies
    _save_raw(session_id, existing)


def get_session_profile(session_id: str) -> dict | None:
    """Load the full session profile."""
    path = _sessions_dir() / f"{session_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_session_profile(
    session_id: str,
    cookies: list[dict] | None = None,
    local_storage: dict[str, str] | None = None,
    fingerprint_seed: int | None = None,
    last_user_agent: str | None = None,
) -> None:
    """Persist full session profile data."""
    existing = get_session_profile(session_id) or {
        "cookies": [],
        "local_storage": {},
        "fingerprint_seed": None,
        "last_user_agent": None,
    }
    if cookies is not None:
        existing["cookies"] = cookies
    if local_storage is not None:
        existing["local_storage"] = local_storage
    if fingerprint_seed is not None:
        existing["fingerprint_seed"] = fingerprint_seed
    if last_user_agent is not None:
        existing["last_user_agent"] = last_user_agent
    _save_raw(session_id, existing)


def _save_raw(session_id: str, data: dict) -> None:
    """Write raw session data to disk."""
    path = _sessions_dir() / f"{session_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def delete_session(session_id: str) -> bool:
    """Delete a session file. Returns ``True`` if it existed."""
    path = _sessions_dir() / f"{session_id}.json"
    if path.is_file():
        path.unlink()
        return True
    return False
