"""Trip schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.itinerary import Itinerary

TRAVEL_STYLES = {"relaxed", "balanced", "adventure", "luxury", "budget", "family"}


class TripCreate(BaseModel):
    destination: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    budget: Decimal = Field(gt=0, le=10_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    travelers: int = Field(default=1, ge=1, le=50)
    travel_style: str = Field(default="balanced")
    interests: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 60:
            raise ValueError("Phase 1 supports trips up to 60 days")
        if self.travel_style not in TRAVEL_STYLES:
            raise ValueError(f"travel_style must be one of {sorted(TRAVEL_STYLES)}")
        return self


class TripUpdate(BaseModel):
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: Decimal | None = None
    travelers: int | None = None
    travel_style: str | None = None
    interests: list[str] | None = None
    status: str | None = None


class TripRead(BaseModel):
    id: uuid.UUID
    destination: str
    start_date: date
    end_date: date
    budget: Decimal
    currency: str
    travelers: int
    travel_style: str
    interests: list[str]
    status: str
    itinerary: Itinerary | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
