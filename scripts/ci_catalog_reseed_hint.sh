#!/usr/bin/env bash
# Emit a reseed reminder when catalog/evidence files change (IMP-009 helper).
# Usage: bash scripts/ci_catalog_reseed_hint.sh [base_ref]
# In GitHub Actions: bash scripts/ci_catalog_reseed_hint.sh "${{ github.event.pull_request.base.sha }}"
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

if [[ -z "$CHANGED" ]]; then
  echo "No catalog/evidence seed files changed — reseed not required."
  exit 0
fi

echo "Catalog/evidence files changed:"
echo "$CHANGED" | sed 's/^/  - /'
echo ""
echo "Run locally when Docker is up: bash scripts/ops_reseed.sh"
echo "Or: HERBAGRAPH_OPS_RESEED=1 bash scripts/ci_gates.sh"
exit 0