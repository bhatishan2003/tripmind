"""Unit tests for the fallback itinerary generator (no LLM key needed)."""

from datetime import date
from decimal import Decimal

from app.services.itinerary_service import generate_itinerary


def test_fallback_itinerary_structure():
    it = generate_itinerary(
        destination="Paris",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 3),
        budget=Decimal(1500),
        currency="USD",
        travelers=2,
        travel_style="balanced",
        interests=["food", "culture"],
    )
    assert len(it.days) == 3
    assert it.total_estimated_cost <= 1500
    assert all(len(d.activities) >= 3 for d in it.days)
    assert it.days[0].day_number == 1
