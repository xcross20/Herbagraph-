#!/usr/bin/env bash
# Optional local browser smoke — skipped in CI unless HERBAGRAPH_PLAYWRIGHT=1 and playwright installed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${HERBAGRAPH_PLAYWRIGHT:-0}" != "1" ]]; then
  echo "SKIP: set HERBAGRAPH_PLAYWRIGHT=1 to run Playwright macrocytic smoke."
  exit 0
fi

if ! python3 -c "import playwright" 2>/dev/null; then
  echo "SKIP: playwright not installed (pip install playwright && playwright install chromium)."
  exit 0
fi

python3 - <<'PY'
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
index = root / "frontend" / "index.html"
if not index.is_file():
    print("FAIL: frontend/index.html missing", file=sys.stderr)
    raise SystemExit(1)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(index.as_uri())
    for section in ("patient-summary", "biological-systems", "recommendations"):
        assert page.locator(f"#{section}").count() == 1, section
    assert page.locator("#regenerate-btn").count() == 1
    browser.close()

print("Playwright macrocytic UI smoke: index sections visible.")
PY