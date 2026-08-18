#!/usr/bin/env bash
# Required PostgreSQL certification. Skips are failures.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${HERBAGRAPH_TEST_POSTGRES:-}" ]]; then
  echo "HERBAGRAPH_TEST_POSTGRES is required" >&2
  exit 1
fi
export HERBAGRAPH_REQUIRE_POSTGRES=1
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
PY="${PYTHON:-python3}"

echo "=== empty-database migration ==="
DATABASE_URL="$HERBAGRAPH_TEST_POSTGRES" "$PY" scripts/ci_postgres_migrate.py --mode empty

echo "=== upgrade from previous supported revision ==="
DATABASE_URL="$HERBAGRAPH_TEST_POSTGRES" "$PY" scripts/ci_postgres_migrate.py --mode upgrade

echo "=== truth-layer PostgreSQL tests (skip = fail) ==="
"$PY" -m pytest tests/discovery_mvp/test_postgres_truth.py tests/discovery_mvp/test_truth_layer_remediation.py::test_two_postgres_sessions_converge_on_one_semantic_finding -q --tb=short
echo "=== postgres-truth ok ==="
