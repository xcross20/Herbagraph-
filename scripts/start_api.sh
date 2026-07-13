#!/usr/bin/env bash
# Railway and other PaaS hosts inject PORT; default to 8000 locally.
set -euo pipefail
PORT="${PORT:-8000}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set. Link Postgres to this Railway service."
  exit 1
fi

echo "DATABASE_URL is configured (driver prefix: ${DATABASE_URL%%://*})."
python3 - <<'PY'
import os
import sys
from urllib.parse import urlparse

url = urlparse(os.environ["DATABASE_URL"])
host = url.hostname or ""
print(f"DB target: {host}:{url.port or 5432}{url.path}")

if os.environ.get("RAILWAY_ENVIRONMENT") and host in ("localhost", "127.0.0.1", "db", ""):
    print(
        "ERROR: DATABASE_URL points at localhost. "
        "In Railway → web service → Variables set:\n"
        "  DATABASE_URL=${{Postgres.DATABASE_PRIVATE_URL}}\n"
        "See railway.env.example",
        file=sys.stderr,
    )
    sys.exit(1)
PY
echo "Applying database migrations (alembic upgrade head)..."
migration_ok=0
for attempt in 1 2 3 4 5; do
  if alembic upgrade head; then
    echo "Migrations applied."
    migration_ok=1
    break
  fi
  echo "Migration attempt $attempt failed; retrying in 5s..."
  sleep 5
done
if [[ "$migration_ok" -ne 1 ]]; then
  echo "WARNING: alembic upgrade head failed — starting API anyway."
  echo "Check DATABASE_URL and run: railway run alembic upgrade head"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"