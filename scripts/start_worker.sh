#!/usr/bin/env bash
# Celery worker entrypoint for Railway (Worker Service).
set -euo pipefail
PORT="${PORT:-8080}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set. Link Postgres to the worker service."
  exit 1
fi
if [[ -z "${REDIS_URL:-}" ]]; then
  echo "ERROR: REDIS_URL is not set. Reference your Redis service on web + worker."
  exit 1
fi

# Railway healthchecks hit /health; Celery has no HTTP server — serve a tiny probe.
python3 - <<PY &
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ.get("PORT", "8080"))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args):
        return

HTTPServer(("0.0.0.0", port), Handler).serve_forever()
PY
health_pid=$!
trap 'kill "$health_pid" 2>/dev/null || true' EXIT

echo "Starting Celery worker (broker: ${REDIS_URL%%@*}@...)"
exec celery -A app.workers.celery_app worker --loglevel=info