#!/usr/bin/env bash
# Live end-to-end smoke against a running Docker stack (api + worker + db + redis).
#
# Catches blindspots pytest cannot: stale Celery worker memory, real HTTP, real task queue.
#
# Usage:
#   docker compose up -d
#   docker compose restart worker api   # after code changes
#   HERBAGRAPH_LIVE_E2E=1 ./scripts/live_e2e_smoke.sh
#
# Optional env:
#   HERBAGRAPH_API_BASE   default http://localhost:8000
#   HERBAGRAPH_SMOKE_FIXTURE  path to upload file (default: tests/fixtures/healow_lipid_panel_excerpt.txt)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${HERBAGRAPH_LIVE_E2E:-0}" != "1" ]]; then
  echo "Set HERBAGRAPH_LIVE_E2E=1 to run live Docker smoke (skipped)."
  exit 0
fi

API_BASE="${HERBAGRAPH_API_BASE:-http://localhost:8000}"
FIXTURE="${HERBAGRAPH_SMOKE_FIXTURE:-$ROOT/tests/fixtures/healow_lipid_panel_excerpt.txt}"
EMAIL="live-e2e-$(date +%s)@example.com"
PASSWORD="LiveE2ePass1"

if [[ ! -f "$FIXTURE" ]]; then
  echo "Missing fixture: $FIXTURE"
  exit 1
fi

echo "=== HerbaGraph live E2E smoke ==="
echo "API: $API_BASE"
echo "Fixture: $FIXTURE"

health_code="$(curl -sf -o /dev/null -w '%{http_code}' "$API_BASE/health" || true)"
if [[ "$health_code" != "200" ]]; then
  echo "FAIL: API not reachable at $API_BASE (health=$health_code)"
  echo "Run: docker compose up -d && docker compose restart worker api"
  exit 1
fi

register_resp="$(curl -sf -X POST "$API_BASE/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"

login_resp="$(curl -sf -X POST "$API_BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"

token="$(python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" <<<"$login_resp")"
auth_hdr="Authorization: Bearer $token"

upload_resp="$(curl -sf -X POST "$API_BASE/api/v1/labs/upload" \
  -H "$auth_hdr" \
  -F "file=@$FIXTURE;filename=healow_smoke.txt;type=text/plain")"

lab_id="$(python3 -c "import json,sys; print(json.load(sys.stdin)['lab_report_id'])" <<<"$upload_resp")"
echo "Uploaded lab_report_id=$lab_id"

for i in $(seq 1 60); do
  lab_json="$(curl -sf -H "$auth_hdr" "$API_BASE/api/v1/labs/$lab_id")"
  status="$(python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" <<<"$lab_json")"
  if [[ "$status" == "complete" ]]; then
    break
  fi
  if [[ "$status" == "failed" ]]; then
    err="$(python3 -c "import json,sys; print(json.load(sys.stdin).get('error_message',''))" <<<"$lab_json")"
    echo "FAIL: lab processing failed: $err"
    exit 1
  fi
  sleep 1
done

if [[ "${status:-}" != "complete" ]]; then
  echo "FAIL: lab processing did not complete in 60s"
  exit 1
fi

python3 - "$lab_json" <<'PY'
import json, sys
lab = json.loads(sys.argv[1])
names = {r["biomarker_name"] for r in lab.get("lab_results", [])}
expected = {"Total Cholesterol", "Triglycerides", "HDL", "LDL", "Non-HDL Cholesterol", "Chol/HDL Ratio"}
missing = expected - names
if missing:
    print(f"FAIL: persisted biomarkers missing catalog names: {sorted(missing)}; got {sorted(names)}")
    sys.exit(1)
print(f"OK: {len(names)} catalog biomarkers persisted")
PY

curl -sf -X POST -H "$auth_hdr" "$API_BASE/api/v1/reports/generate/$lab_id" >/dev/null

for i in $(seq 1 90); do
  lab_json="$(curl -sf -H "$auth_hdr" "$API_BASE/api/v1/labs/$lab_id")"
  stage="$(python3 -c "import json,sys; print(json.load(sys.stdin).get('report_stage',''))" <<<"$lab_json")"
  if [[ "$stage" == "complete" ]]; then
    report_id="$(python3 -c "import json,sys; print(json.load(sys.stdin)['latest_report_id'])" <<<"$lab_json")"
    break
  fi
  if [[ "$stage" == "failed" ]]; then
    err="$(python3 -c "import json,sys; print(json.load(sys.stdin).get('report_error_message',''))" <<<"$lab_json")"
    echo "FAIL: report generation failed: $err"
    exit 1
  fi
  sleep 1
done

if [[ "${stage:-}" != "complete" || -z "${report_id:-}" ]]; then
  echo "FAIL: report generation did not complete in 90s (stage=${stage:-unknown})"
  exit 1
fi

report_json="$(curl -sf -H "$auth_hdr" "$API_BASE/api/v1/reports/$report_id")"

python3 - "$report_json" <<'PY'
import json, sys
body = json.loads(sys.argv[1])
measured = body["biomarker_summary"]["measured_biomarkers"]
unresolved = [
    m["biomarker_name"]
    for m in measured
    if m["status"] in ("low", "high", "critical_low", "critical_high") and not m["in_catalog"]
]
if unresolved:
    print(f"FAIL: unresolved abnormal biomarkers: {unresolved}")
    sys.exit(1)
recs = body.get("recommendations") or []
if not recs:
    print("FAIL: report has zero recommendations")
    sys.exit(1)
pathways = body.get("pathway_activations") or []
if not pathways:
    print("FAIL: report has zero pathway activations")
    sys.exit(1)
print(f"OK: report complete — {len(recs)} recommendations, {len(pathways)} pathways, 0 unresolved abnormals")
PY

echo "=== Live E2E smoke passed ==="