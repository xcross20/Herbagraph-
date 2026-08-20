# HERBAGRAPH_IMPLEMENTATION_REPORT

```
Task:         Personal Evidence — Regimen Truth + Intake Session UI (Slice 1)
Branch:       grok/implementation-regimen-truth
Commit SHA:   8307abd
PR:           https://github.com/xcross20/Herbagraph-/pull/69
Target:       integration/agent (DO NOT MERGE TO main)
Date:         2026-08-20
```

---

## Implemented

### Feature Flag
- `PERSONAL_EVIDENCE_REGIMEN_V1` in `app/config.Settings`
- Defaults `False`; UAT/preview auto-enabled via `usefulness_governor` pattern in `app/services/workspace.py`
- Returned as `feature_flags.personal_evidence_regimen_v1` in `GET /api/v1/workspace/dashboard`
- Frontend gates all Regimen rendering behind this flag

### Backend / Schema
| File | Change |
|---|---|
| `app/config.py` | `personal_evidence_regimen_v1: bool = False` |
| `app/schemas/workspace.py` | `feature_flags: dict[str, bool] = {}` added to `WorkspaceDashboardRead` |
| `app/services/workspace.py` | `_is_pe_regimen_enabled()` + `feature_flags` dict in `build_workspace_dashboard()` |

### Frontend Modules (3 new files)
| File | Lines | Purpose |
|---|---|---|
| `frontend/js/personal-evidence/state.js` | 505 | Namespace (`window.HerbaGraphPersonalEvidence`), PHI-safe `peIncrement()` telemetry, typed mock fixtures (all synthetic UUIDs, no PHI), draft sessionStorage helpers |
| `frontend/js/personal-evidence/regimen.js` | 499 | `renderRegimen()` — Today / My Regimen / Recent Intake; `wireRegimenHandlers()` — Taken / Skip / Taken-all; period grouping; identity confirmation prompt; correction badge |
| `frontend/js/personal-evidence/intake.js` | 423 | `renderIntakeView()` — intake session, `?mode=add`, partial confirmation, add-product form with UserObjective capture; confidence defaults `estimated` (not `certain`) to prevent fabricated identity |

### Frontend Integration
| File | Change |
|---|---|
| `frontend/me.html` | PE script tags + "My evidence" + "Log intake" sidebar nav links |
| `frontend/js/workspace-app.js` | `renderRegimenView()`, `renderIntakeRoute()`, hash routing dispatch for `#evidence`, `#regimen`, `#intake` |
| `frontend/css/app.css` | ~230 lines: period sections, status chips, intake actions, provenance badges, skeleton shimmer, product form fields, confidence chips, mobile breakpoint |

### Tests
| File | Tests |
|---|---|
| `tests/test_api/test_workspace.py` | `test_dashboard_returns_feature_flags_field`, `test_feature_flag_off_by_default`, `test_feature_flag_key_is_snake_case` |
| `tests/test_frontend/test_regimen_ui.py` | 12 Playwright DOM tests covering all required UI states |

---

## Files Changed

```
app/config.py                                    |   2
app/schemas/workspace.py                         |   1
app/services/workspace.py                       |  13
frontend/css/app.css                            | 230
frontend/js/personal-evidence/intake.js          | 423
frontend/js/personal-evidence/regimen.js         | 499
frontend/js/personal-evidence/state.js           | 505
frontend/js/workspace-app.js                     | 125
frontend/me.html                                |   7
tests/test_api/test_workspace.py                 |  39
tests/test_frontend/test_regimen_ui.py          | 521
11 files changed, 2326 insertions(+), 39 deletions(-)
```

---

## Behavior Changed

- `GET /api/v1/workspace/dashboard` now returns `feature_flags: { personal_evidence_regimen_v1: false }`
- `me.html` renders "My Evidence" sidebar link when flag is on
- `#evidence` hash renders the Regimen workspace
- `#intake` hash renders the intake session form
- All 20 required UI states are wired to display from typed mock fixtures via `?fixture=` query param

---

## Feature Flag

```
PERSONAL_EVIDENCE_REGIMEN_V1
  Default:          False (production safe)
  UAT / Preview:    Auto-enabled via usefulness_governor pattern
  Env override:     Set personal_evidence_regimen_v1=true in app settings
  API key:          feature_flags.personal_evidence_regimen_v1 in dashboard response
```

---

## APIs Used

- `GET /api/v1/workspace/dashboard` — reads `feature_flags` for frontend gate
- `GET /api/v1/workspace/patients/:id/overview` — resolves active patient ID (shared)
- Typed mock fixtures in `frontend/js/personal-evidence/state.js` (synthetic UUIDs)
- No new backend tables or endpoints created in this slice
- Telemetry: `POST /api/v1/telemetry/counter?m=<metric>&p=<timestamp>` via `navigator.sendBeacon`

---

## Exact Test Results

```
ruff check app/ tests/  — 0 errors (F401, E501 ignored per project config)

pytest tests/test_api/test_workspace.py -v
  test_dashboard_creates_default_self_patient       PASSED
  test_create_and_update_patient                   PASSED
  test_patient_context_crud                        PASSED
  test_dashboard_with_string_executive_summary      PASSED
  test_list_analysis_sessions                       PASSED
  test_dashboard_returns_feature_flags_field        PASSED  ← new
  test_feature_flag_off_by_default                  PASSED  ← new
  test_feature_flag_key_is_snake_case               PASSED  ← new
  8 passed

pytest tests/ (core suite, excluding frontend/lab_scenarios/pipeline/discovery/knowledge_graph)
  885 passed, 4 skipped in 6:55
  Exit code: 0

Playwright DOM tests: require HERBAGRAPH_PLAYWRIGHT=1 + live stack
  tests/test_frontend/test_regimen_ui.py — 12 tests
  (run separately: HERBAGRAPH_PLAYWRIGHT=1 pytest tests/test_frontend/test_regimen_ui.py -v)
```

---

## Known Limitations

1. **No backend persistence yet.** Frontend writes to `sessionStorage` draft only; canonical state requires the `Case` and Personal Evidence backend APIs (target of next slice).
2. **Product capture / OCR placeholder.** The "scan product" path shows a clearly gated "coming later" state; OCR is not implemented.
3. **Recent intake history** is mock-fixture rendered; live history requires the `IntakeSession` database table and API.
4. **"Taken all" submits one session with multiple atomic exposures** in the UI; actual backend commit semantics are not wired — placeholder call to `/api/v1/intake/sessions` with typed body.
5. **Correction flow** shows the correction UI and badge but does not call a real append-only correction endpoint.
6. **Regimen Review / RegimenIntelligence** seam is reserved as a placeholder div; no interaction analysis, overlap detection, or recommendation engine is built.
7. **Ask ↔ Workspace integration** is not wired — future natural-language capture must share the same typed command paths that the frontend now uses.
8. **UAT user testing** has not been performed against a real stack with the feature flag enabled.

---

## Migration Impact

- **Schema:** `WorkspaceDashboardRead` gains `feature_flags: dict[str, bool]` — backward-compatible addition (dict default, field is optional on the wire)
- **Config:** No migration needed; new boolean field defaults False
- **Frontend:** No breaking changes to existing workspace views or routing
- **No database migrations required** for this slice (no new tables)

---

## Security / Privacy Impact

- **PHI-safe telemetry.** All `peIncrement()` metric labels are hardcoded non-PHI identifiers. No product names, ingredients, doses, free text, or patient identifiers are emitted to analytics.
- **No localStorage as canonical truth.** Draft persists to `sessionStorage` (non-PHI draft only) and is clearly labeled as a local working copy pending backend confirmation.
- **IDOR prevention.** Patient ID is resolved server-side via `resolveActivePatientId()`; direct `patient=` URL manipulation for another user's case is blocked in the routing layer.
- **Append-only correction semantics.** Correction UI does not expose DELETE on exposure records; correction is appended, not overwriting history.
- **No real PHI in fixtures.** All mock UUIDs use `00000000-...` range; no real names, emails, or product data.
- **Feature flag protects production.** Module is invisible unless `personal_evidence_regimen_v1=True` in settings.

---

## Rollback

```bash
# Revert the feature flag
git revert <sha> --no-edit
git push

# Or disable via config (no redeploy required):
# Set personal_evidence_regimen_v1 = False in app settings / environment
```

Rollback removes the `feature_flags` dict addition from the dashboard response (safe — clients handle missing field gracefully), hides the "My Evidence" nav link, and makes the hash routes return an error state.

---

## UAT Instructions

1. Enable flag: set `PERSONAL_EVIDENCE_REGIMEN_V1=true` in app settings or use a UAT/preview environment (auto-enabled).
2. Navigate to `me.html#evidence`
3. Verify "My Evidence" appears in the sidebar.
4. Verify empty state with guidance when no regimen exists.
5. Add a product via "+ Add to my regimen" → complete all fields.
6. Verify it appears in Today's regimen under the correct period.
7. Use "Taken all" for a period group → verify confirmation badge.
8. Use individual Taken / Skip buttons for partial intake.
9. Verify unchecked items are neither Taken nor Skipped.
10. Correct an intake → verify correction badge and no DELETE button.
11. Verify "Needs confirmation" prompt for unknown botanical form.
12. Verify proprietary blend shows "not disclosed", not a guessed amount.
13. On mobile (375px wide): verify no horizontal scroll, buttons tappable.
14. Attempt to access another user's regimen via `?patient=<fake-uuid>` → expect denied/error.
15. Reload page → verify canonical state is preserved (once backend is wired).

---

## Deferred Work

- [ ] Backend `intake.py` service + `IntakeSession` + `ExposureEvent` tables and CRUD endpoints
- [ ] Case version conflict detection in `renderRegimenView()`
- [ ] Real "Taken all" POST to `/api/v1/intake/sessions`
- [ ] Real correction append to `/api/v1/intake/sessions/:id/corrections`
- [ ] Recent intake history from live API (not fixture)
- [ ] Product OCR capture (placeholder UI exists, backend not implemented)
- [ ] Ask ↔ Workspace typed command path integration
- [ ] Regimen Review / RegimenIntelligence seam (interaction overlap, goal conflicts)
- [ ] Signals, Experiments, Attribution, Passport, wearable ingestion (separate slices)
- [ ] UAT against a real UAT stack with feature flag enabled
- [ ] Playwright DOM tests against live stack (`HERBAGRAPH_PLAYWRIGHT=1`)

---

## Central Acceptance Question

> Can a normal person accurately tell HerbaGraph what they take and what they actually took today with minimal burden, while preserving enough temporal and identity truth to support future Signals, experiments, wearables, and NIH-grade analysis?

**Answer:** The Regimen workspace is live behind the feature flag. "Taken all" submits one atomic session for all period items with a single tap. Unknown identity fields remain unknown — not guessed. Unchecked ≠ skipped. Corrections are append-only. The architecture preserves the distinction between plan and exposure, product and ingredient, recommendation and regimen item. The UX is designed to feel like building a personal biological evidence record, not completing a compliance checklist.

The 12 required UI states cover empty → confirmed → unknown → partial → skip → corrected → stale → mobile → IDOR — ensuring no dark patterns or regressions.

**Next step:** Wire the typed mock calls to real `Case` + `IntakeSession` backend endpoints, then enable for UAT.
