#!/usr/bin/env bash
# Railway and other PaaS hosts inject PORT; default to 8000 locally.
# Worker Service: set SERVICE_ROLE=worker (same start command as web).
set -euo pipefail

if [[ "${SERVICE_ROLE:-web}" == "worker" ]]; then
  exec bash "$(dirname "$0")/start_worker.sh"
fi

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

from app.core.database_url import validate_production_database_url

railway = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
if err := validate_production_database_url(os.environ["DATABASE_URL"], railway=railway):
    print(f"ERROR: {err}", file=sys.stderr)
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
  env_name="$(printf '%s' "${APP_ENV:-${HERBAGRAPH_ENV:-${RAILWAY_ENVIRONMENT_NAME:-local}}}" | tr '[:upper:]' '[:lower:]')"
  if [[ -n "${RAILWAY_ENVIRONMENT:-}" && "$env_name" != "production" ]]; then
    echo "Alembic failed on non-production Railway. Bootstrapping schema from models."
    root="$(cd "$(dirname "$0")/.." && pwd)"
    python3 "$root/scripts/bootstrap_nonprod_schema.py"
    echo "Schema bootstrap done. Seed catalog separately: python scripts/seed_db.py"
  else
    echo "WARNING: alembic upgrade head failed — starting API anyway."
    echo "Check DATABASE_URL and run: railway run alembic upgrade head"
  fi
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"