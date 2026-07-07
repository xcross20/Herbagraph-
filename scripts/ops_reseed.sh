#!/usr/bin/env bash
# Reseed the knowledge graph when Docker is running (ops workflow).
# Safe to run after tier_a_evidence, biomarker catalog, or food link changes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== HerbaGraph Ops Reseed ==="

echo "[1/2] Validating seed catalog counts..."
python3 scripts/validate_seed_counts.py

if ! docker compose ps --status running --services 2>/dev/null | grep -qx api; then
    echo "[2/2] SKIP: Docker api service not running."
    echo "      Start stack: docker compose up -d"
    echo "      Then run: docker compose exec api python scripts/reseed_db.py"
    exit 0
fi

echo "[2/2] Reseeding PostgreSQL knowledge graph via Docker..."
docker compose exec -T api python scripts/reseed_db.py

echo "=== Reseed complete ==="