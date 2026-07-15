#!/usr/bin/env bash
# One-time Railway production bootstrap — run after Postgres + Redis are linked.
# Usage: railway link && bash scripts/railway_bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v railway >/dev/null 2>&1; then
  echo "Install Railway CLI: npm install -g @railway/cli"
  echo "Then: railway login && railway link"
  exit 1
fi

echo "=== HerbaGraph Railway bootstrap ==="
echo "[1/2] Alembic migrations..."
railway run alembic upgrade head
echo "[2/3] Knowledge graph reseed..."
railway run python scripts/reseed_db.py
echo "[3/3] Canonical registry bootstrap (Tier A from interventions)..."
railway run python scripts/bootstrap_canonical_registry.py
echo "=== Done. Smoke test: curl \$(railway domain)/health ==="