# AI Travel Planner

[![CI](https://img.shields.io/github/actions/workflow/status/bhatishan2003/tripmind/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white)](https://github.com/bhatishan2003/tripmind/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/bhatishan2003/tripmind/ci.yml?branch=main&label=tests%20passing&logo=pytest&logoColor=white)](https://github.com/bhatishan2003/tripmind/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/bhatishan2003/tripmind/branch/main/graph/badge.svg)](https://codecov.io/gh/bhatishan2003/tripmind)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python&logoColor=white)](https://github.com/bhatishan2003/tripmind/blob/main/pyproject.toml)

End-to-end trip creation with LLM-generated (or template fallback) day-by-day
itineraries, grounded in a local knowledge base (RAG) with source citations.

## Stack
FastAPI · PostgreSQL + pgvector (async SQLAlchemy) · Alembic · JWT auth ·
sentence-transformers embeddings · Groq/OpenAI (structured JSON) with offline fallback ·
React + Vite + Tailwind frontend

## Quickstart (one command)

Starts Postgres, the FastAPI backend, and the React frontend together:

```bash
./run.sh
```

Open http://localhost:5173 (API docs at http://localhost:8000/docs).
Demo login: `demo@example.com` / `demo1234`. See `./run.sh --help` for flags
(`--no-db`, `--no-frontend`, `--reset-db`, …).

### Manual quickstart

```bash
cp .env.example .env
docker compose up -d db            # start Postgres
pip install -e ".[dev]"
uvicorn app.main:app --reload      # creates tables automatically in local env
# in another terminal:
cd frontend && npm install && npm run dev
```

Seed demo data (no LLM key needed):
```bash
python scripts/seed_database.py
```

Ingest the knowledge base (chunks + embeddings into pgvector):
```bash
python scripts/ingest_knowledge.py
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
| GET | `/destinations/search` | Search RAG destinations (`?q=`) |
| GET | `/destinations/{name}` | Destination knowledge-base detail |

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

## RAG / knowledge base

Documents in `data/documents/` are cleaned, chunked, embedded with
`sentence-transformers` (`all-MiniLM-L6-v2`, no API key), and stored in pgvector.
Every itinerary is generated with the top-k retrieved chunks injected as context,
and the response includes an `itinerary.sources` array (title, snippet, score) that
the UI shows as citations. Retrieval runs through `app/rag/retriever.py` and is
best-effort: with an empty corpus the itinerary is generated ungrounded.

The embeddings fall back to a deterministic hash vector when the model cannot be
downloaded, so ingestion and tests work fully offline.
