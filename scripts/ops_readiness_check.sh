#!/usr/bin/env bash
# Backend readiness checklist — run before handing the API to users or integrators.
# Does not require a production frontend; validates API/worker/DB/catalog health.
#
#   ./scripts/ops_readiness_check.sh
#   ./scripts/ops_readiness_check.sh --strict   # fail on warnings too

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STRICT=0
if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
fi

API_BASE="${HERBAGRAPH_API_BASE:-http://localhost:8000}"
WARN=0
FAIL=0

warn() { echo "  WARN: $*"; WARN=$((WARN + 1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL + 1)); }
ok()   { echo "  OK:   $*"; }

echo "=== HerbaGraph backend readiness ==="
echo "API: $API_BASE"
echo ""

echo "[1] Environment file"
if [[ -f .env ]]; then
  ok ".env present"
  for key in SECRET_KEY ENCRYPTION_KEY DATABASE_URL REDIS_URL NCBI_EMAIL; do
    if ! grep -q "^${key}=" .env 2>/dev/null; then
      fail ".env missing $key"
    fi
  done
  if grep -q "^SECRET_KEY=change_me" .env 2>/dev/null || grep -q "^SECRET_KEY=insecure" .env 2>/dev/null; then
    warn "SECRET_KEY still looks like a placeholder"
  fi
  if grep -q "^ENCRYPTION_KEY=$" .env 2>/dev/null; then
    fail "ENCRYPTION_KEY is empty (run: python scripts/generate_encryption_key.py)"
  fi
  if grep -q "^OPENAI_API_KEY=$" .env 2>/dev/null; then
    warn "OPENAI_API_KEY empty — reports use catalog-only reasoning (slower evidence fetch still runs)"
  fi
  if grep -q "^DEBUG=true" .env 2>/dev/null; then
    warn "DEBUG=true — CORS is wide open; use DEBUG=false in production"
  fi
else
  fail ".env missing (copy .env.example)"
fi

echo ""
echo "[2] Docker services"
if command -v docker >/dev/null 2>&1 && docker compose ps --status running --services 2>/dev/null | grep -q .; then
  for svc in db redis api worker; do
    if docker compose ps --status running --services 2>/dev/null | grep -qx "$svc"; then
      ok "docker $svc running"
    else
      fail "docker $svc not running"
    fi
  done
else
  warn "Docker compose stack not running (local non-Docker deploys may skip this)"
fi

echo ""
echo "[3] API health"
health_code="$(curl -sf -o /tmp/hg_health.json -w '%{http_code}' "$API_BASE/health" 2>/dev/null || echo "000")"
if [[ "$health_code" == "200" ]]; then
  ok "GET /health → 200"
  python3 -c "import json; d=json.load(open('/tmp/hg_health.json')); assert d.get('status')=='ok'" 2>/dev/null || warn "/health body unexpected"
else
  fail "GET /health → $health_code (is api running?)"
fi

ready_code="$(curl -sf -o /tmp/hg_ready.json -w '%{http_code}' "$API_BASE/ready" 2>/dev/null || echo "000")"
if [[ "$ready_code" == "200" ]]; then
  ok "GET /ready → 200 (database connected)"
elif [[ "$ready_code" == "503" ]]; then
  fail "GET /ready → 503 (database unreachable or migrations missing)"
else
  fail "GET /ready → $ready_code"
fi

echo ""
echo "[4] Catalog + pipeline gates"
for script in validate_seed_counts.py audit_pipeline_resilience.py audit_unresolved_abnormals.py; do
  if python3 "scripts/$script" >/tmp/hg_gate.out 2>&1; then
    ok "$script"
  else
    fail "$script (see /tmp/hg_gate.out)"
  fi
done

echo ""
echo "[5] Database seed (when Docker api is up)"
if docker compose ps --status running --services 2>/dev/null | grep -qx api; then
  if docker compose exec -T api python scripts/seed_db.py 2>/tmp/hg_seed.err | grep -qiE "already seeded|seeded [0-9]+ biomarkers"; then
    ok "knowledge graph seeded"
  else
    warn "seed check inconclusive — run: docker compose exec api python scripts/reseed_db.py"
  fi
else
  warn "skipped DB seed check (api container not running)"
fi

echo ""
echo "[6] Smoke uploads (optional — set HERBAGRAPH_LIVE_E2E=1)"
if [[ "${HERBAGRAPH_LIVE_E2E:-0}" == "1" ]] && [[ "$health_code" == "200" ]] && [[ -x scripts/live_e2e_smoke.sh ]]; then
  if bash scripts/live_e2e_smoke.sh 2>/tmp/hg_live.err; then
    ok "live_e2e_smoke.sh"
  else
    warn "live_e2e_smoke failed — run: docker compose restart worker api && HERBAGRAPH_LIVE_E2E=1 ./scripts/live_e2e_smoke.sh"
  fi
else
  warn "skipped live upload smoke (export HERBAGRAPH_LIVE_E2E=1 to enable)"
fi

echo ""
echo "[7] UI smoke (optional — set HERBAGRAPH_PLAYWRIGHT=1)"
if [[ "${HERBAGRAPH_PLAYWRIGHT:-0}" == "1" ]] && [[ "$health_code" == "200" ]] && [[ -x scripts/playwright_ui_smoke.sh ]]; then
  if bash scripts/playwright_ui_smoke.sh 2>/tmp/hg_pw.err; then
    ok "playwright_ui_smoke.sh"
  else
    warn "playwright UI smoke failed — pip install playwright && playwright install chromium"
  fi
else
  warn "skipped Playwright UI smoke (export HERBAGRAPH_PLAYWRIGHT=1 to enable)"
fi

echo ""
echo "=== Summary ==="
echo "Failures: $FAIL"
echo "Warnings: $WARN"
if [[ "$FAIL" -gt 0 ]]; then
  echo "NOT READY — fix failures above"
  exit 1
fi
if [[ "$STRICT" -eq 1 && "$WARN" -gt 0 ]]; then
  echo "NOT READY (strict) — resolve warnings"
  exit 1
fi
echo "Backend readiness: OK (warnings=$WARN)"
exit 0