#!/usr/bin/env bash
# Celery worker entrypoint for Railway (Worker Service).
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set. Link Postgres to the worker service."
  exit 1
fi
if [[ -z "${REDIS_URL:-}" ]]; then
  echo "ERROR: REDIS_URL is not set. Reference your Redis service on web + worker."
  exit 1
fi

echo "Starting Celery worker (broker: ${REDIS_URL%%@*}@...)"
exec celery -A app.workers.celery_app worker --loglevel=info