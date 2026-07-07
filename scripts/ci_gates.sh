#!/usr/bin/env bash
# HerbaGraph mandatory CI gates — definition of done from ops/BACKLOG.json
# Run from repo root: ./scripts/ci_gates.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== HerbaGraph CI Gates ==="

echo "[1/10] ruff check..."
ruff check app tests

echo "[2/10] pathway coverage (all catalog biomarkers)..."
python3 scripts/validate_pathway_coverage.py

echo "[3/10] alias resolution audit..."
python3 scripts/audit_alias_resolution.py

echo "[4/10] evidence gap audit (priority pathways)..."
python3 scripts/audit_evidence_gaps.py

echo "[5/10] PMID integrity audit..."
python3 scripts/audit_pmid_integrity.py

echo "[6/10] lab scenario matrix..."
python3 scripts/validate_lab_scenarios.py

echo "[7/10] scenario matrix coverage audit..."
python3 scripts/audit_scenario_coverage.py

echo "[8/10] seed catalog counts..."
python3 scripts/validate_seed_counts.py

echo "[9/10] sample lab files parse..."
python3 scripts/validate_sample_labs.py

echo "[10/10] pytest full suite..."
python3 -m pytest tests/ -q --tb=line

if [[ "${HERBAGRAPH_OPS_RESEED:-0}" == "1" ]]; then
  echo ""
  bash scripts/ops_reseed.sh
fi

echo "=== All gates passed ==="