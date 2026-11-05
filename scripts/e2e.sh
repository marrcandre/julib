#!/usr/bin/env bash
set -euo pipefail
# Dedicated disposable database only. Never point this command at production.
: "${DATABASE_URL:?Set DATABASE_URL to a disposable local/CI PostgreSQL database}"
export DEBUG=true ALLOWED_EMAILS=marco@example.com,ju@example.com ADMIN_EMAIL=marco@example.com
export CSRF_TRUSTED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
mkdir -p .superpowers
uv run --project backend python backend/manage.py migrate --noinput > .superpowers/e2e-migrate.log
uv run --project backend python scripts/e2e_session.py
uv run --project backend python backend/manage.py runserver 127.0.0.1:8000 --noreload > .superpowers/e2e-api.log 2>&1 &
api_pid=$!
npm run dev --prefix frontend -- --port 5173 --strictPort > .superpowers/e2e-vite.log 2>&1 &
web_pid=$!
trap 'kill "$api_pid" "$web_pid" 2>/dev/null || true' EXIT
for attempt in {1..30}; do
  if curl -fs http://127.0.0.1:8000/api/v1/health >/dev/null && curl -fs http://127.0.0.1:5173/ >/dev/null; then break; fi
  sleep 1
done
python scripts/camera_fixture.py .superpowers/isbn-camera.y4m
export CAMERA_FIXTURE="$PWD/.superpowers/isbn-camera.y4m"
npm run test:e2e --prefix frontend
