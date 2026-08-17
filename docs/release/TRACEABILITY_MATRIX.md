# Traceability matrix (PR-A revision 2)

Status vocabulary: not started | written, unverified | locally verified | CI verified | staging verified | founder accepted

Claim labels: `reproduced on main` | `scaffolded` | `reproduced on pinned V2 branch`

V2 forensic SHA: `e7ab37aeed5538546fd657a6b0c1a394ad937510`

| ID | Claim | Implementation | Unit | Integration | E2E | Tripwire | Status | Evidence | Label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DI-01 | Stable identity + active/history | absent on main | `test_finding_identity_survives_rebuild` | — | E2E-03 | — | written, unverified | this PR | reproduced on main |
| DI-05 | Replay does not change semantic state | absent on main | `test_second_rebuild_is_not_a_new_truth` (IDs, timestamps, no churn) | — | E2E-04 | — | written, unverified | this PR | reproduced on main |
| DI-06 | Concurrent workers cannot duplicate active identity | absent on main | `test_postgres_concurrent_writers_cannot_duplicate_active_identity` | PG only | — | duplicate-active-identity | written, unverified | skip on SQLite | scaffolded |
| DI-09a | Correction retains original history | absent on integration | `test_correction_preserves_original_history` | — | E2E-03 | history-deletion | written, unverified | xfail: live path deletes original | reproduced on integration |
| DI-09b | Replacement links to actual original | absent on integration | `test_correction_links_replacement_and_excludes_inactive_history_from_all_active_projections` | PR-D required | E2E-03 | inverted-fk | written, unverified | explicit skip; no linkage model/path | scaffolded |
| DI-10 | Inactive facts stay out of active prompts/maps/reports | absent on integration | same PR-D contract test | PR-D required | E2E-03 | inactive-in-projection | written, unverified | explicit skip; cannot be proved after deletion | scaffolded |
| DI-13 | `not_applicable` creates no edge | V2 only, flags off | `test_not_applicable_creates_no_evidence_relationship` | V2 persist tests | E2E-02 | unrelated-edge | written, unverified | skip until seam exists | scaffolded |
| DI-14 | Non-addressing cannot close | V2 only, flags off | `test_does_not_directly_assess_maps_to_does_not_address` + branch-close skip | V2 persist tests | E2E-01 | close-on-non-address | written, unverified | skip | scaffolded |
| SO-02 | No diagnosis / disease probability | partial (copy) | map keys, `DiscoveryHypothesisRead`, `snapshot_to_read`, frontend render | — | E2E-01 | — | written, unverified | this PR | reproduced on main |
| SO-10 | Prior test explains coverage | V2 coverage seed only | mapping tests | — | E2E-01 | silent coverage loss | not started on main | | scaffolded |
| DG-03 | Recognized tests have coverage semantics | `app/coverage` on V2 branch | mapping tests | — | E2E-01 | — | not started on main | | scaffolded |
| ISS-01 | Coverage enum ≠ evidence enum | V2 only | mapping skip tests | — | — | — | written, unverified | V2 forensic | reproduced on pinned V2 branch |
| ISS-02 | Unrelated evidence not attached (`not_applicable` ≠ `inconclusive`) | V2 only | `test_unrelated_emg_must_not_attach_to_biliary_persist_path` | — | E2E-02 | — | written, unverified | skip; V2 forensic | reproduced on pinned V2 branch |
| ISS-03 | Identity/uniqueness (Issue 3) | absent on main | `test_postgres_unique_active_finding_identity` | PG | — | — | written, unverified | skip on SQLite | scaffolded |
| ISS-04 | Correction direction: `original_claim_id` → original | absent on integration | PR-D correction contract test | PR-D required | — | inverted-fk | written, unverified | explicit skip | scaffolded; reproduced only on pinned V2 |
| ISS-05 | Replacement points at predecessor | absent on integration | PR-D correction contract test | PR-D required | — | — | written, unverified | explicit skip | scaffolded; reproduced only on pinned V2 |
| ISS-06 | Active-only projection | absent on integration | PR-D correction contract test | PR-D required | — | inactive-in-projection | written, unverified | explicit skip | scaffolded; reproduced only on pinned V2 |
| ISS-07 | Replay / no identity churn | absent on main | second rebuild ID stability | — | — | — | written, unverified | this PR | reproduced on main |
| ISS-08 | Branch closing through governor | V2 only | `test_non_addressing_evidence_cannot_close_branch` | — | E2E-01 | — | written, unverified | skip | scaffolded |
| ISS-09 | Concurrency / source-event identity persisted | absent on main | PG concurrent-writer definition | PG | — | — | written, unverified | skip on SQLite | scaffolded |
| E2E-01 | Burning feet + normal EMG | conversation only | — | — | not started | — | not started | | not started |
| E2E-02 | Gallbladder + unrelated EMG | conversation only | safety tests on main | — | not started | — | not started | | not started |
| E2E-07 | Safety escalation persists | `safety_json` on main | `test_safety_nuance` | API | not started | — | locally verified (unit) | a1e82f1 | reproduced on main |
| RL-01 | Required CI green including persist | CI now targets `integration/agent`; persist tests xfail-strict | — | — | — | — | written, unverified | `.github/workflows/ci.yml` | scaffolded |

No item has been skipped to complete. Nothing is CI verified for the truth
layer. Production SHA, runtime flags, and migration state are unknown.
Persistent UAT SHA at last verified check: `843dd55c715b`. Current integration
base after PR #18: `7132b5121d20cb749b6208419f154374e0c040e6`.
Reviewed Grok PR-A predecessor: `d048fe855fe2179ec16f757ba065c07f96d78ec2`.
Repaired Codex PR-A evidence commit:
`2590b1af20936bd1cec369478fa7d659a8a1a8c0`. A metadata-only follow-up records
that SHA; exact-SHA CI remains required before merge.
