#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/web"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# ── Helpers ───────────────────────────────────────────────────────────────────

free_port() {
  local port=$1
  local pids
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "  Port $port in use — killing existing process(es): $pids"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi
}

# ── Activate virtualenv ───────────────────────────────────────────────────────
if [ ! -d "$ROOT/.venv" ]; then
  echo "No .venv found. Run 'bash setup.sh' from $ROOT first."
  exit 1
fi
source "$ROOT/.venv/bin/activate"

# ── Install web-specific Python deps ─────────────────────────────────────────
pip install --quiet -r "$WEB/requirements-web.txt"

# ── Frontend deps ─────────────────────────────────────────────────────────────
FRONTEND="$WEB/frontend"
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "Installing frontend dependencies (npm install)…"
  (cd "$FRONTEND" && npm install)
fi

# ─────────────────────────────────────────────────────────────────────────────

if [ "${1:-dev}" = "prod" ]; then
  echo "Building frontend for production…"
  (cd "$FRONTEND" && npm run build)
  echo ""
  free_port "$BACKEND_PORT"
  echo "Starting server at http://localhost:$BACKEND_PORT"
  cd "$ROOT" && uvicorn web.server:app --host 0.0.0.0 --port "$BACKEND_PORT"

else
  # Dev mode: backend + Vite dev server side by side
  free_port "$BACKEND_PORT"
  free_port "$FRONTEND_PORT"

  echo ""
  echo "Starting backend  →  http://localhost:$BACKEND_PORT"
  echo "Starting frontend →  http://localhost:$FRONTEND_PORT"
  echo ""

  # Backend in background; capture its PID
  cd "$ROOT" && uvicorn web.server:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload &
  BACKEND_PID=$!

  # Kill backend and any leftover children on exit / Ctrl-C
  cleanup() {
    echo ""
    echo "Shutting down…"
    kill "$BACKEND_PID" 2>/dev/null || true
    free_port "$BACKEND_PORT"
    free_port "$FRONTEND_PORT"
  }
  trap cleanup INT TERM EXIT

  # Frontend dev server in foreground
  cd "$FRONTEND" && npm run dev
fi
