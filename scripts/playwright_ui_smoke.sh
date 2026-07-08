#!/usr/bin/env bash
# Playwright browser smoke — upload lab fixtures through the real UI.
#
# Requires a running Docker stack (api + worker + db + redis).
#
#   pip install playwright
#   playwright install chromium
#   docker compose up -d && docker compose restart worker api
#   HERBAGRAPH_PLAYWRIGHT=1 ./scripts/playwright_ui_smoke.sh
#
# Optional:
#   HERBAGRAPH_UI_BASE=http://localhost:8000

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${HERBAGRAPH_PLAYWRIGHT:-0}" != "1" ]]; then
  echo "SKIP: set HERBAGRAPH_PLAYWRIGHT=1 to run Playwright UI smoke."
  exit 0
fi

if ! python3 -c "import playwright" 2>/dev/null; then
  echo "SKIP: pip install playwright && playwright install chromium"
  exit 0
fi

API_BASE="${HERBAGRAPH_UI_BASE:-http://localhost:8000}"
health_code="$(curl -sf -o /dev/null -w '%{http_code}' "$API_BASE/health" 2>/dev/null || true)"
if [[ "$health_code" != "200" ]]; then
  echo "FAIL: API not reachable at $API_BASE (health=$health_code)"
  echo "Run: docker compose up -d && docker compose restart worker api"
  exit 1
fi

export HERBAGRAPH_PLAYWRIGHT=1
export HERBAGRAPH_UI_BASE="$API_BASE"

echo "=== HerbaGraph Playwright UI smoke ==="
echo "UI: $API_BASE"

python3 -m pytest tests/test_frontend/test_playwright_ui_smoke.py -v --tb=short

echo "=== Playwright UI smoke passed ==="