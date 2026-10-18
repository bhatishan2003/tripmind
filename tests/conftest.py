"""Shared test configuration — keeps the suite offline and deterministic.

The app falls back to a template itinerary only when no LLM key is configured.
Developers often have GROQ_API_KEY/OPENAI_API_KEY in their local `.env`, which
would make tests hit a real provider (slow, flaky, non-deterministic). Force the
offline generator for every test.
"""

import pytest

from app.services import itinerary_service


@pytest.fixture(autouse=True)
def _disable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(itinerary_service, "_resolve_llm", lambda: None)
