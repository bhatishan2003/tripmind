"""Trip repository."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.trip import Trip


async def list_by_user(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
) -> tuple[list[Trip], int]:
    total = (await session.execute(select(func.count()).select_from(Trip).where(Trip.user_id == user_id))).scalar_one()
    result = await session.execute(
        select(Trip).where(Trip.user_id == user_id).order_by(Trip.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def get_owned(session: AsyncSession, user_id: uuid.UUID, trip_id: uuid.UUID) -> Trip | None:
    result = await session.execute(select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, **fields) -> Trip:
    trip = Trip(**fields)
    session.add(trip)
    await session.commit()
    await session.refresh(trip)
    return trip


async def save(session: AsyncSession, trip: Trip) -> Trip:
    session.add(trip)
    await session.commit()
    await session.refresh(trip)
    return trip


async def delete(session: AsyncSession, trip: Trip) -> None:
    await session.delete(trip)
    await session.commit()
