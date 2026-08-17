# Traceability matrix (initial)

Status vocabulary: not started | written, unverified | locally verified | CI verified | staging verified | founder accepted

| ID | Claim | Implementation | Unit | Integration | E2E | Tripwire | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DI-01 | Stable identity + active/history | absent on main | `test_finding_identity_survives_rebuild` | — | E2E-03 | — | written, unverified | this PR |
| DI-05 | Replay does not change semantic state | absent on main | `test_second_rebuild_is_not_a_new_truth` | — | E2E-04 | — | written, unverified | this PR |
| DI-10 | Inactive facts stay out of projection | absent on main | `test_projection_must_not_use_deleted_history` | — | E2E-03 | inactive-in-projection | written, unverified | this PR |
| DI-13 | `not_applicable` creates no edge | V2 only, flags off | `test_not_applicable_creates_no_evidence_relationship` | V2 persist tests | E2E-02 | unrelated-edge | written, unverified | this PR; import fails on main |
| DI-14 | Non-addressing cannot close | V2 only, flags off | `test_does_not_directly_assess_maps_to_does_not_address` | V2 persist tests | E2E-01 | close-on-non-address | written, unverified | this PR |
| SO-02 | No diagnosis / disease probability | partial (copy) | `test_map_payload_must_not_carry_diagnostic_certainty` | — | E2E-01 | — | written, unverified | this PR |
| SO-10 | Prior test explains coverage | V2 coverage seed only | mapping tests | — | E2E-01 | silent coverage loss | not started on main | |
| DG-03 | Recognized tests have coverage semantics | `app/coverage` on V2 branch | mapping tests | — | E2E-01 | — | not started on main | |
| E2E-01 | Burning feet + normal EMG | conversation only | — | — | not started | — | not started | |
| E2E-02 | Gallbladder + unrelated EMG | conversation only | safety tests on main | — | not started | — | not started | |
| E2E-07 | Safety escalation persists | `safety_json` on main | `test_safety_nuance` | API | not started | — | locally verified (unit) | a1e82f1 |
| RL-01 | Required CI green including persist | CI does not run persist suite | — | — | — | — | not started | `.github/workflows/ci.yml` |

No item has been skipped to complete. Nothing is CI verified for the truth layer.
