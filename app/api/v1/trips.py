"""Trip CRUD + itinerary endpoints (Phase 1 core)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import not_found
from app.db.database import get_session
from app.db.models.user import User
from app.db.repositories import trip as trip_repo
from app.schemas.trip import TripCreate, TripRead, TripUpdate
from app.services import trip_service

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: TripCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    return await trip_service.create_trip(session, current.id, payload)


@router.get("", response_model=list[TripRead])
async def list_trips(
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    trips, _total = await trip_repo.list_by_user(session, current.id, limit=limit, offset=offset)
    return trips


@router.get("/{trip_id}", response_model=TripRead)
async def get_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    return await trip_service.get_trip(session, current.id, trip_id)


@router.patch("/{trip_id}", response_model=TripRead)
async def patch_trip(
    trip_id: uuid.UUID,
    payload: TripUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    return await trip_service.update_trip(session, current.id, trip_id, payload)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    trip = await trip_repo.get_owned(session, current.id, trip_id)
    if not trip:
        raise not_found("Trip not found")
    await trip_repo.delete(session, trip)


@router.post("/{trip_id}/generate", response_model=TripRead)
async def regenerate(
    trip_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    """Regenerate the day-by-day itinerary with current trip constraints."""
    return await trip_service.regenerate_itinerary(session, current.id, trip_id)
