"""CRUD endpoints for stealth profiles."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.stealth import StealthProfile
from ..storage.profiles import (
    delete_profile,
    get_profile,
    list_profiles,
    save_profile,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[StealthProfile])
async def list_profiles_endpoint() -> list[StealthProfile]:
    return list_profiles()


@router.get("/{profile_id}", response_model=StealthProfile)
async def get_profile_endpoint(profile_id: str) -> StealthProfile:
    profile = get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("", response_model=StealthProfile, status_code=201)
async def create_profile_endpoint(profile: StealthProfile) -> StealthProfile:
    return save_profile(profile)


@router.put("/{profile_id}", response_model=StealthProfile)
async def update_profile_endpoint(profile_id: str, profile: StealthProfile) -> StealthProfile:
    profile.id = profile_id
    return save_profile(profile)


@router.delete("/{profile_id}")
async def delete_profile_endpoint(profile_id: str) -> dict:
    if not delete_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"deleted": True}
