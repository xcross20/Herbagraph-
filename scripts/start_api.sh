#!/usr/bin/env bash
# Railway and other PaaS hosts inject PORT; default to 8000 locally.
set -euo pipefail
PORT="${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"