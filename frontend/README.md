# React Frontend — AI Travel Planner

Interactive single-page app for the Phase 1 FastAPI backend (in `../app`).
Replaces the previous Streamlit UI.

**Stack:** Vite · React 18 · TypeScript · Tailwind CSS · React Router · lucide-react

## Setup

```bash
cd travelling-agent/frontend
npm install
```

Requires Node.js 18+.

## Run

Backend first (default `http://localhost:8000`):

```bash
# terminal 1 (backend, from travelling-agent/)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# terminal 2 (frontend, from travelling-agent/frontend/)
npm run dev
```

Open http://localhost:5173.

The dev server proxies `/api/*` to the backend (see `vite.config.ts`). To point at a
different backend, copy `.env.example` to `.env` and set:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the dev server with HMR |
| `npm run build` | Typecheck + production build into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run typecheck` | Run `tsc --noEmit` |

## Views

| Route | What it does | Backend calls |
|---|---|---|
| `/login` | Login + register tabs, JWT stored in `localStorage` | `POST /api/v1/auth/{login,register}`, `GET /api/v1/auth/me` |
| `/` | Trip list with live filter + sort, skeleton loaders, empty state | `GET /api/v1/trips` |
| `/chat` | Streaming chat pane with saved conversation history | `POST /api/v1/chat` (SSE), `GET /api/v1/chat/{id}` |
| `/trips/new` | Validated form; animated generation progress while waiting | `POST /api/v1/trips` |
| `/trips/:id` | Day-by-day accordion itinerary, regenerate, edit, delete, export | `GET/PATCH/DELETE /api/v1/trips/{id}`, `POST /api/v1/trips/{id}/generate` |

## Interactive features

- **Dark mode** toggle (persisted to `localStorage`, honours OS preference).
- **Export / Print** — expands every day and opens the browser print dialog, backed by
  a dedicated `@media print` stylesheet for a clean PDF.
- **Streaming chat assistant** — SSE tokens rendered live, saved conversations,
  inline RAG citations, stop-generation, and a "New chat" reset.
- Animated itinerary **generation progress** with rotating status messages.
- **Collapsible day plans**, a timeline of activities with category badges and costs.
- **Toasts** for success/error feedback, modal-based edit and delete confirmation.
- **Backend health** indicator, trip search/sort, loading skeletons, fully responsive.

## Structure

```
src/
  api/client.ts          Typed fetch client (ApiError, timeouts, JWT, SSE streaming)
  context/               Auth, Theme, and Toast providers
  components/            AppShell, ChatPane, ItineraryView, TripCard, Modal, ...
  pages/                 LoginPage, TripsPage, ChatPage, NewTripPage, TripDetailsPage
  lib/                   constants (styles/currencies/interests) and formatters
  types.ts               Shared API types
```

Demo login (after `python ../scripts/seed_database.py`): `demo@example.com` / `demo1234`
