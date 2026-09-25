"""Seed a demo user + trip (uses fallback itinerary, no LLM key needed)."""

import asyncio
from datetime import date
from decimal import Decimal

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal
from app.db.repositories import user as user_repo
from app.schemas.trip import TripCreate
from app.services import trip_service


async def main() -> None:
    async with AsyncSessionLocal() as session:
        user = await user_repo.get_by_email(session, "demo@example.com")
        if not user:
            user = await user_repo.create(
                session,
                email="demo@example.com",
                hashed_password=hash_password("demo1234"),
                full_name="Demo Traveler",
            )
            print(f"created user {user.email}")
        trip = await trip_service.create_trip(
            session,
            user.id,
            TripCreate(
                destination="Barcelona",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 4),
                budget=Decimal(1800),
                currency="USD",
                travelers=2,
                travel_style="balanced",
                interests=["food", "culture", "beaches"],
            ),
        )
        print(f"created trip {trip.id} -> {trip.destination} ({len(trip.itinerary['days'])} days)")


if __name__ == "__main__":
    asyncio.run(main())
