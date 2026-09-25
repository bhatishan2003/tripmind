"""Trip orchestration: CRUD + itinerary generation."""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import bad_request, not_found
from app.db.models.trip import Trip
from app.db.repositories import trip as trip_repo
from app.schemas.trip import TripCreate, TripUpdate
from app.services.itinerary_service import generate_itinerary


async def create_trip(session: AsyncSession, user_id: uuid.UUID, payload: TripCreate) -> Trip:
    itinerary = generate_itinerary(
        destination=payload.destination,
        start_date=payload.start_date,
        end_date=payload.end_date,
        budget=payload.budget,
        currency=payload.currency,
        travelers=payload.travelers,
        travel_style=payload.travel_style,
        interests=payload.interests,
    )
    trip = await trip_repo.create(
        session,
        user_id=user_id,
        destination=payload.destination,
        start_date=payload.start_date,
        end_date=payload.end_date,
        budget=payload.budget,
        currency=payload.currency,
        travelers=payload.travelers,
        travel_style=payload.travel_style,
        interests=payload.interests,
        status="planned",
        itinerary=itinerary.model_dump(),
    )
    return trip


async def get_trip(session: AsyncSession, user_id: uuid.UUID, trip_id: uuid.UUID) -> Trip:
    trip = await trip_repo.get_owned(session, user_id, trip_id)
    if not trip:
        raise not_found("Trip not found")
    return trip


async def update_trip(session: AsyncSession, user_id: uuid.UUID, trip_id: uuid.UUID, payload: TripUpdate) -> Trip:
    trip = await get_trip(session, user_id, trip_id)
    data = payload.model_dump(exclude_unset=True)
    if "end_date" in data or "start_date" in data:
        start = data.get("start_date", trip.start_date)
        end = data.get("end_date", trip.end_date)
        if end < start:
            raise bad_request("end_date must be on or after start_date")
    for key, value in data.items():
        if isinstance(value, Decimal):
            setattr(trip, key, value)
        else:
            setattr(trip, key, value)
    return await trip_repo.save(session, trip)


async def regenerate_itinerary(session: AsyncSession, user_id: uuid.UUID, trip_id: uuid.UUID) -> Trip:
    trip = await get_trip(session, user_id, trip_id)
    itinerary = generate_itinerary(
        destination=trip.destination,
        start_date=trip.start_date,
        end_date=trip.end_date,
        budget=trip.budget,
        currency=trip.currency,
        travelers=trip.travelers,
        travel_style=trip.travel_style,
        interests=list(trip.interests or []),
    )
    trip.itinerary = itinerary.model_dump()
    return await trip_repo.save(session, trip)
