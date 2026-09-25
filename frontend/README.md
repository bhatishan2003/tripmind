# Streamlit Frontend — AI Travel Planner

Separate frontend for the Phase 1 FastAPI backend (`../app`).

## Setup

```bash
cd travelling-agent/frontend
pip install -r requirements.txt
```

## Run

Backend must be running first (default `http://localhost:8000`):

```bash
# terminal 1 (backend, from travelling-agent/)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# terminal 2 (frontend, from travelling-agent/frontend/)
streamlit run app.py
```

Open http://localhost:8501.

Point at a different backend:

```bash
API_BASE_URL=http://localhost:8000 streamlit run app.py
```

or change **Backend URL** in the sidebar.

## Pages (single-file app)

| View | What it does | Backend call |
|---|---|---|
| Login / Register | JWT auth, stores token in session | `POST /api/v1/auth/*`, `GET /api/v1/auth/me` |
| My Trips | List + filter + open trip cards | `GET /api/v1/trips` |
| ＋ New Trip | Form → create + generate itinerary | `POST /api/v1/trips` |
| 🧾 Trip Details | Itinerary day-by-day, regenerate, edit (PATCH), delete, raw JSON | `GET/PATCH/DELETE /api/v1/trips/{id}`, `POST /api/v1/trips/{id}/generate` |

## Files

- `app.py` — full Streamlit UI
- `api_client.py` — `TravelApiClient` (requests wrapper, raises `ApiError`)
- `requirements.txt` — `streamlit`, `requests`
- `.streamlit/config.toml` — port + theme

Demo login (after `python ../scripts/seed_database.py`): `demo@example.com` / `demo1234`
