#!/usr/bin/env bash
# Reseed PostgreSQL when seed catalog files change (IMP-009 / GHA main-branch job).
# Usage:
#   bash scripts/ci_reseed_postgres.sh [base_ref]
#   HERBAGRAPH_FORCE_RESEED=1 bash scripts/ci_reseed_postgres.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASE_REF="${1:-}"
CATALOG_GLOBS=(
  "app/knowledge_graph/tier_a_catalog.py"
  "app/knowledge_graph/tier_a_evidence.py"
  "app/knowledge_graph/lifestyle_evidence.py"
  "app/knowledge_graph/biomarker_catalog.py"
  "app/knowledge_graph/food_compound_links.py"
  "app/knowledge_graph/seed_data.py"
  "app/knowledge_graph/peptide_catalog.py"
)

if [[ -n "$BASE_REF" ]] && git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  CHANGED="$(git diff --name-only "$BASE_REF"...HEAD -- "${CATALOG_GLOBS[@]}" || true)"
else
  CHANGED="$(git status --porcelain -- "${CATALOG_GLOBS[@]}" | awk '{print $2}' || true)"
fi

if [[ -z "$CHANGED" ]] && [[ "${HERBAGRAPH_FORCE_RESEED:-0}" != "1" ]]; then
  echo "No catalog/evidence seed files changed — reseed skipped."
  exit 0
fi

export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://herbagraph:herbagraph@localhost:5432/herbagraph}"

echo "=== HerbaGraph CI Postgres Reseed ==="
if [[ -n "$CHANGED" ]]; then
  echo "Changed catalog files:"
  echo "$CHANGED" | sed 's/^/  - /'
fi

echo "[1/3] Validating seed catalog counts..."
python3 scripts/validate_seed_counts.py

echo "[2/3] Waiting for PostgreSQL..."
connected=0
for _ in $(seq 1 30); do
  if python3 - <<'PY'
import asyncio
import os

async def probe() -> None:
    import asyncpg
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url, timeout=2)
    await conn.close()

asyncio.run(probe())
PY
  then
    connected=1
    break
  fi
  sleep 2
done
if [[ "$connected" -eq 0 ]]; then
  echo "FAIL: PostgreSQL not reachable at ${DATABASE_URL}"
  exit 1
fi

echo "[3/3] Reseeding knowledge graph..."
python3 scripts/reseed_db.py

echo "=== CI Postgres reseed complete ==="