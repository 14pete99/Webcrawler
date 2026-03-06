"""Session management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.session import SessionInfo
from ..storage.sessions import delete_session, list_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionInfo])
async def list_sessions_endpoint() -> list[SessionInfo]:
    return list_sessions()


@router.delete("/{session_id}")
async def delete_session_endpoint(session_id: str) -> dict:
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}
