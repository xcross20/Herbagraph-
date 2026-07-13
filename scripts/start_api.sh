#!/usr/bin/env bash
# Railway and other PaaS hosts inject PORT; default to 8000 locally.
set -euo pipefail
PORT="${PORT:-8000}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set. Link Postgres to this Railway service."
  exit 1
fi

echo "DATABASE_URL is configured (driver prefix: ${DATABASE_URL%%://*})."
echo "Applying database migrations (alembic upgrade head)..."
for attempt in 1 2 3 4 5; do
  if alembic upgrade head; then
    echo "Migrations applied."
    break
  fi
  if [[ "$attempt" -eq 5 ]]; then
    echo "ERROR: alembic upgrade head failed after 5 attempts."
    exit 1
  fi
  echo "Migration attempt $attempt failed; retrying in 5s..."
  sleep 5
done

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"