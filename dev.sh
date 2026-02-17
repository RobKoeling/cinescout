#!/usr/bin/env bash
# Start backend API, admin panel, and frontend dev server.
# Press Ctrl+C to stop all processes.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill 0
}
trap cleanup SIGINT SIGTERM

echo "Starting backend API      → http://localhost:8000"
(cd "$ROOT/backend" && source .venv/bin/activate && uvicorn cinescout.main:app --reload) &

echo "Starting admin panel      → http://localhost:8001/admin"
(cd "$ROOT/backend" && source .venv/bin/activate && uvicorn cinescout.admin.app:admin_app --port 8001 --reload) &

echo "Starting frontend         → http://localhost:5173"
(cd "$ROOT/frontend" && npm run dev) &

wait
