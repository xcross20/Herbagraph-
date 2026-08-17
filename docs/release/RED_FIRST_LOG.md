# Red-first log — Milestone 1

**Branch:** `grok/mvp-baseline-red-tests`  
**Command:** `.venv/bin/python -m pytest tests/discovery_mvp -q --tb=line`  
**Result:** 6 failed, 1 passed in 0.22s  
**Date:** 2026-08-17

| Test | Failure | Violated invariant | Intended? |
| --- | --- | --- | --- |
| `test_finding_identity_survives_rebuild` | `assert None is not None` (original finding id gone after `rebuild_case`) | DI-01 / ADR-MVP-001 | yes — `apply_snapshot` deletes rows |
| `test_projection_must_not_use_deleted_history` | original `onset=after surgery` row is `None` after `apply_snapshot` | DI-10 / ADR-MVP-004 | yes — history is destroyed, not inactivated |
| `test_second_rebuild_is_not_a_new_truth` | passed | DI-05 (weak form) | rebuild currently recreates one row from extras; not proof of identity stability |
| `test_not_applicable_creates_no_evidence_relationship` | `ModuleNotFoundError: app.discovery.evidence_mapping` (and no `epistemics` on this branch) | DI-13 / ADR-MVP-002 | yes on `integration/agent` — mapping seam is absent |
| `test_unknown_coverage_creates_no_evidence_relationship` | same import failure | DI-13 | yes |
| `test_does_not_directly_assess_maps_to_does_not_address` | same import failure | DI-14 / ADR-MVP-002 | yes |
| `test_map_payload_must_not_carry_diagnostic_certainty` | `'certainty' not in` snapshot map payload | SO-02 | yes — `build_map_payload` still emits `certainty` |

No production behavior was changed to obtain these failures.

Note: persist Issues 1–9 from the V2 review cannot be reproduced on this branch because those modules are not on `main`/`integration/agent`. They were reproduced and then repaired on `origin/discovery/investigation-state-v2` @ `e7ab37a` (unmerged, flags off). That repair is **not** part of this PR.
