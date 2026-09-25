# AI Travel Planner — Phase 1: Basic Travel Planner

End-to-end trip creation with LLM-generated (or template fallback) day-by-day itineraries.
No agents, no RAG yet — those land in Phase 2.

## Stack
FastAPI · PostgreSQL (async SQLAlchemy) · Alembic · JWT auth · OpenAI (structured JSON) with offline fallback

## Quickstart

```bash
cp .env.example .env
docker compose up -d db            # start Postgres
pip install -e ".[dev]"
uvicorn app.main:app --reload      # creates tables automatically in local env
```

Seed demo data (no LLM key needed):
```bash
python scripts/seed_database.py
```

Run tests (SQLite, no external services):
```bash
pytest -q
```

## API (prefix `/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create user |
| POST | `/auth/login` | Get JWT |
| GET | `/auth/me` | Current user |
| POST | `/trips` | Create trip + generate itinerary |
| GET | `/trips` | List my trips |
| GET | `/trips/{id}` | Trip detail + itinerary |
| PATCH | `/trips/{id}` | Update constraints |
| DELETE | `/trips/{id}` | Delete trip |
| POST | `/trips/{id}/generate` | Regenerate itinerary |

### Example

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"demo1234"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST localhost:8000/api/v1/trips \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{
    "destination": "Kyoto", "start_date": "2026-04-01", "end_date": "2026-04-04",
    "budget": "2200.00", "currency": "USD", "travelers": 2,
    "travel_style": "balanced", "interests": ["culture", "food", "nature"]
  }' | python -m json.tool
```

## LLM integration
Groq is the default provider (OpenAI-compatible endpoint, no extra dependency).
Set in `.env`:
```bash
GROQ_API_KEY=gsk_...            # get one at https://console.groq.com/keys
GROQ_MODEL=llama-3.3-70b-versatile
LLM_PROVIDER=auto               # auto | groq | openai
```
OpenAI still works as an alternative (`OPENAI_API_KEY` / `OPENAI_MODEL`).
Without any key the service uses a deterministic template so the full flow works
offline; it still respects dates, budget, travelers, style, and interests, and
returns the same `Itinerary` schema the LLM path validates against.

## What's next (Phase 2)
`agents/` (planner/researcher/budget/validator graph), `rag/` (embeddings + vector store),
`tools/` (weather/maps/places/flights/hotels), chat + destination endpoints.
