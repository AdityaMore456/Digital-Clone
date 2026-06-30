#!/usr/bin/env bash
# Starts backend (FastAPI/uvicorn) and frontend (Vite) together.
set -euo pipefail
cd "$(dirname "$0")"

cleanup() {
  echo "Stopping servers..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Starting backend on http://localhost:8000"
( cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 ) &
BACKEND_PID=$!

echo "==> Starting frontend on http://localhost:5173"
( cd frontend && npm run dev -- --port 5173 ) &
FRONTEND_PID=$!

wait
