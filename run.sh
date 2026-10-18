#!/usr/bin/env bash
#
# run.sh — start the whole AI Travel Planner stack with one command.
#
#   Postgres (docker)  ->  FastAPI backend  ->  React (Vite) frontend
#
# Usage:
#   ./run.sh                 # start db + backend + frontend (seeds demo user once)
#   ./run.sh --no-db         # reuse an already-running database
#   ./run.sh --no-frontend   # backend only
#   ./run.sh --no-backend    # frontend only (expects backend already up)
#   ./run.sh --no-seed       # skip demo-data seeding
#   ./run.sh --reset-db      # WIPE the database volume, then start fresh
#   ./run.sh -h | --help     # this help
#
# Press Ctrl+C once to stop the backend and frontend (the database keeps
# running so the next start is fast; stop it with: docker compose stop db).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ----------------------------------------------------------------- config
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
BACKEND_LOG="${TMPDIR:-/tmp}/travel-agent-backend.log"

START_DB=1
START_BACKEND=1
START_FRONTEND=1
SEED=1
RESET_DB=0

# ------------------------------------------------------------------- colors
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BLUE=$'\033[34m'
  RESET=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi
log()  { printf '%s==>%s %s\n' "$BLUE$BOLD" "$RESET" "$*"; }
ok()   { printf '%s  ok%s %s\n' "$GREEN$BOLD" "$RESET" "$*"; }
warn() { printf '%s   !%s %s\n' "$YELLOW$BOLD" "$RESET" "$*"; }
die()  { printf '%s   x%s %s\n' "$RED$BOLD" "$RESET" "$*" >&2; exit 1; }

usage() {
  sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

# ------------------------------------------------------------------- args
while [ $# -gt 0 ]; do
  case "$1" in
    --no-db)       START_DB=0 ;;
    --no-backend)  START_BACKEND=0 ;;
    --no-frontend) START_FRONTEND=0 ;;
    --no-seed)     SEED=0 ;;
    --reset-db)    RESET_DB=1 ;;
    -h|--help)     usage ;;
    *) die "Unknown option: $1 (try --help)" ;;
  esac
  shift
done

# --------------------------------------------------------------- helpers
port_in_use() { nc -z 127.0.0.1 "$1" >/dev/null 2>&1; }

wait_for_port() { # host port timeout_seconds label
  local port="$1" timeout="${2:-30}" label="${3:-service}" i=0
  until nc -z 127.0.0.1 "$port" >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -ge "$timeout" ] && return 1
    sleep 1
  done
  ok "$label is up on port $port"
}

DC=""
docker_cmd() {
  if [ -z "$DC" ]; then
    if docker info >/dev/null 2>&1; then
      DC="docker"
    elif sudo -n docker info >/dev/null 2>&1; then
      DC="sudo docker"
    else
      # last resort: ask for the password interactively
      DC="sudo docker"
    fi
  fi
  $DC "$@"
}

BACKEND_PID=""
CLEANED=0
cleanup() {
  local code=$?
  [ "$CLEANED" -eq 1 ] && return 0
  CLEANED=1
  echo
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Stopping backend (pid $BACKEND_PID)…"
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  printf '%sStack stopped.%s Database container left running "travel-db".\n' "$DIM" "$RESET"
  exit "$code"
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------- preflight
log "Checking prerequisites"

[ -f "$ROOT/.env" ] || {
  warn ".env not found — copying from .env.example"
  cp "$ROOT/.env.example" "$ROOT/.env"
}

if [ ! -x "$PY" ]; then
  warn ".venv not found — creating it with python3"
  python3 -m venv "$VENV" || die "Could not create virtualenv (is python3 installed?)"
fi
ok "Python: $("$PY" --version 2>&1)"

if ! "$PY" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  log "Installing backend dependencies (pip install -e '.[dev]')…"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -e ".[dev]" || die "pip install failed"
fi
ok "Backend dependencies present"

if [ "$START_FRONTEND" -eq 1 ]; then
  command -v node >/dev/null 2>&1 || die "node not found on PATH"
  command -v npm  >/dev/null 2>&1 || die "npm not found on PATH"
  ok "Node $(node --version) / npm $(npm --version)"
fi

if [ "$START_BACKEND" -eq 1 ] && port_in_use "$BACKEND_PORT"; then
  die "Port $BACKEND_PORT is already in use — stop the other process or set BACKEND_PORT"
fi
if [ "$START_FRONTEND" -eq 1 ] && port_in_use "$FRONTEND_PORT"; then
  die "Port $FRONTEND_PORT is already in use — stop the other process or set FRONTEND_PORT"
fi

# ---------------------------------------------------------------- database
if [ "$RESET_DB" -eq 1 ]; then
  warn "--reset-db: removing the database volume (all data will be lost)"
  docker_cmd compose down -v >/dev/null 2>&1 || true
fi

if [ "$START_DB" -eq 1 ]; then
  log "Starting Postgres (docker compose)"
  if ! docker_cmd compose up -d db; then
    die "Could not start Postgres. Is Docker running? (see RUN_PROJECT.txt for the docker-group fix)"
  fi
  wait_for_port 5432 40 "Postgres" || die "Postgres did not open port 5432 in time"
else
  warn "Skipping database start (--no-db)"
fi

# ------------------------------------------------------- schema + seed
if [ "$START_BACKEND" -eq 1 ]; then
  log "Ensuring database schema exists"
  "$PY" - <<'PY' || die "Could not initialise the schema — is Postgres running? (do not pass --no-db on a fresh start)"
import asyncio
from app.db.database import Base, engine
import app.db.models  # noqa: F401  (register tables)

async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(main())
PY
  ok "Schema ready"

  if [ "$SEED" -eq 1 ]; then
    if "$PY" - <<'PY'
import asyncio, sys
from app.db.database import AsyncSessionLocal
from app.db.repositories import user as user_repo

async def main() -> None:
    async with AsyncSessionLocal() as s:
        user = await user_repo.get_by_email(s, "demo@example.com")
        sys.exit(0 if user else 1)

asyncio.run(main())
PY
    then
      ok "Demo user already present — skipping seed"
    else
      log "Seeding demo data (demo@example.com / demo1234)"
      "$PY" scripts/seed_database.py
    fi
  fi
fi

# ---------------------------------------------------------------- backend
if [ "$START_BACKEND" -eq 1 ]; then
  log "Starting backend -> http://localhost:$BACKEND_PORT  (docs: /docs)"
  "$PY" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload \
    >"$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!

  if wait_for_port "$BACKEND_PORT" 40 "Backend"; then
    ok "Backend log: $BACKEND_LOG"
  else
    warn "Backend did not respond in time — last log lines:"
    tail -n 20 "$BACKEND_LOG" || true
    die "Backend failed to start"
  fi
else
  warn "Skipping backend (--no-backend)"
fi

# --------------------------------------------------------------- frontend
if [ "$START_FRONTEND" -eq 1 ]; then
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    log "Installing frontend dependencies (npm install)…"
    npm --prefix "$ROOT/frontend" install || die "npm install failed"
  fi

  echo
  printf '%s===================== AI Travel Planner is running =====================%s\n' "$BOLD$GREEN" "$RESET"
  printf '  Frontend : %s\n' "${BLUE}http://localhost:${FRONTEND_PORT}${RESET}"
  printf '  Backend  : %s   (API docs at /docs)\n' "${BLUE}http://localhost:${BACKEND_PORT}${RESET}"
  printf '  Login    : demo@example.com / demo1234\n'
  printf '%sPress Ctrl+C to stop.%s\n' "$DIM" "$RESET"
  printf '%s========================================================================%s\n\n' "$BOLD$GREEN" "$RESET"

  npm --prefix "$ROOT/frontend" run dev -- --port "$FRONTEND_PORT" --host
else
  log "Frontend skipped (--no-frontend). Backend is running; press Ctrl+C to stop."
  wait "$BACKEND_PID" 2>/dev/null || true
fi
