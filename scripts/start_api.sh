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
from urllib.parse import urlparse
url = urlparse(os.environ["DATABASE_URL"])
print(f"DB target: {url.hostname}:{url.port or 5432}{url.path}")
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