#!/usr/bin/env bash
# Mandatory Discovery MVP packet. Inherited catalog/scenario redness is out of scope.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
if [[ -x /Users/immanuellewis/herbagraph/.venv/bin/python ]]; then
  PY=/Users/immanuellewis/herbagraph/.venv/bin/python
fi
"$PY" -m pytest tests/discovery_mvp tests/test_discovery tests/test_api/test_discovery_cases.py tests/test_api/test_discovery_layer.py -q --tb=line
echo "discovery_mvp_gates_ok"
