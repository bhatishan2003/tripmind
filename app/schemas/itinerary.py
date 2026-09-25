"""Structured itinerary output (LLM contract + API response)."""

from pydantic import BaseModel, Field


class Activity(BaseModel):
    time: str = Field(examples=["09:00"])
    title: str
    description: str = ""
    location: str = ""
    category: str = Field(default="sightseeing", examples=["food", "culture", "nature", "nightlife"])
    cost_estimate: float = 0.0


class DayPlan(BaseModel):
    day_number: int
    date: str = Field(examples=["2026-05-01"])
    theme: str = ""
    activities: list[Activity] = Field(default_factory=list)
    meals: list[str] = Field(default_factory=list)
    notes: str = ""


class Itinerary(BaseModel):
    summary: str
    total_estimated_cost: float
    currency: str = "USD"
    days: list[DayPlan]
