# Traceability matrix (PR-A revision 2)

Status vocabulary: not started | written, unverified | locally verified | CI verified | staging verified | founder accepted

Claim labels: `reproduced on main` | `scaffolded` | `reproduced on pinned V2 branch`

V2 forensic SHA: `e7ab37aeed5538546fd657a6b0c1a394ad937510`

| ID | Claim | Implementation | Unit | Integration | E2E | Tripwire | Status | Evidence | Label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DI-01 | Stable identity + active/history | absent on main | `test_finding_identity_survives_rebuild` | — | E2E-03 | — | written, unverified | this PR | reproduced on main |
| DI-05 | Replay does not change semantic state | absent on main | `test_second_rebuild_is_not_a_new_truth` (IDs, timestamps, no churn) | — | E2E-04 | — | written, unverified | this PR | reproduced on main |
| DI-06 | Concurrent workers cannot duplicate active identity | absent on main | `test_postgres_concurrent_writers_cannot_duplicate_active_identity` | PG only | — | duplicate-active-identity | written, unverified | skip on SQLite | scaffolded |
| DI-09 | Correction retains original + replacement + correct links | absent on main | `test_correction_inactivates_original_and_excludes_it_from_projection` | — | E2E-03 | inverted-fk | written, unverified | this PR | reproduced on main |
| DI-10 | Inactive facts stay out of projection | absent on main | same correction test: map/API/snapshot exclude old value while row remains | — | E2E-03 | inactive-in-projection | written, unverified | this PR | reproduced on main |
| DI-13 | `not_applicable` creates no edge | V2 only, flags off | `test_not_applicable_creates_no_evidence_relationship` | V2 persist tests | E2E-02 | unrelated-edge | written, unverified | skip until seam exists | scaffolded |
| DI-14 | Non-addressing cannot close | V2 only, flags off | `test_does_not_directly_assess_maps_to_does_not_address` + branch-close skip | V2 persist tests | E2E-01 | close-on-non-address | written, unverified | skip | scaffolded |
| SO-02 | No diagnosis / disease probability | partial (copy) | map keys, `DiscoveryHypothesisRead`, `snapshot_to_read`, frontend render | — | E2E-01 | — | written, unverified | this PR | reproduced on main |
| SO-10 | Prior test explains coverage | V2 coverage seed only | mapping tests | — | E2E-01 | silent coverage loss | not started on main | | scaffolded |
| DG-03 | Recognized tests have coverage semantics | `app/coverage` on V2 branch | mapping tests | — | E2E-01 | — | not started on main | | scaffolded |
| ISS-01 | Coverage enum ≠ evidence enum | V2 only | mapping skip tests | — | — | — | written, unverified | V2 forensic | reproduced on pinned V2 branch |
| ISS-02 | Unrelated evidence not attached (`not_applicable` ≠ `inconclusive`) | V2 only | `test_unrelated_emg_must_not_attach_to_biliary_persist_path` | — | E2E-02 | — | written, unverified | skip; V2 forensic | reproduced on pinned V2 branch |
| ISS-03 | Identity/uniqueness (Issue 3) | absent on main | `test_postgres_unique_active_finding_identity` | PG | — | — | written, unverified | skip on SQLite | scaffolded |
| ISS-04 | Correction direction: `original_claim_id` → original | absent on main | correction test `supersedes_finding_id` | — | — | — | written, unverified | this PR (main deletes instead) | reproduced on main |
| ISS-05 | Replacement linkage: replacement points at original | absent on main | same correction test | — | — | — | written, unverified | this PR | reproduced on main |
| ISS-06 | Active-only projection | absent on main | correction test excludes inactive value | — | — | — | written, unverified | this PR | reproduced on main |
| ISS-07 | Replay / no identity churn | absent on main | second rebuild ID stability | — | — | — | written, unverified | this PR | reproduced on main |
| ISS-08 | Branch closing through governor | V2 only | `test_non_addressing_evidence_cannot_close_branch` | — | E2E-01 | — | written, unverified | skip | scaffolded |
| ISS-09 | Concurrency / source-event identity persisted | absent on main | PG concurrent-writer definition | PG | — | — | written, unverified | skip on SQLite | scaffolded |
| E2E-01 | Burning feet + normal EMG | conversation only | — | — | not started | — | not started | | not started |
| E2E-02 | Gallbladder + unrelated EMG | conversation only | safety tests on main | — | not started | — | not started | | not started |
| E2E-07 | Safety escalation persists | `safety_json` on main | `test_safety_nuance` | API | not started | — | locally verified (unit) | a1e82f1 | reproduced on main |
| RL-01 | Required CI green including persist | CI now targets `integration/agent`; persist tests xfail-strict | — | — | — | — | written, unverified | `.github/workflows/ci.yml` | scaffolded |

No item has been skipped to complete. Nothing is CI verified for the truth layer. Production and staging SHAs are unknown.
