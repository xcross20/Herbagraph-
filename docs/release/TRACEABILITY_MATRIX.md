# Traceability matrix (PR-A closeout after PR #33)

Status vocabulary: not started | written, unverified | locally verified | CI verified | staging verified | founder accepted

Claim labels: `reproduced on main` | `scaffolded` | `reproduced on pinned V2 branch`

V2 forensic SHA: `e7ab37aeed5538546fd657a6b0c1a394ad937510`

| ID | Claim | Implementation | Unit | Integration | E2E | Tripwire | Status | Evidence | Label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DI-01 | Stable identity + active/history | absent on main | `test_finding_identity_survives_rebuild` | — | E2E-03 | — | written, unverified | this PR | reproduced on main |
| DI-05 | Replay does not change semantic state | absent on main | `test_second_rebuild_is_not_a_new_truth` (IDs, timestamps, no churn) | — | E2E-04 | — | written, unverified | this PR | reproduced on main |
| DI-06 | Concurrent workers cannot duplicate active identity | absent on integration | `test_postgres_concurrent_writers_cannot_duplicate_active_identity` | PR-C required | — | duplicate-active-identity | written, unverified | unconditional skip; no harness | scaffolded |
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
| ISS-03 | Identity/uniqueness (Issue 3) | absent on integration | `test_postgres_unique_active_finding_identity` | PR-C required | — | — | written, unverified | unconditional skip; no harness | scaffolded |
| ISS-04 | Correction direction: `original_claim_id` → original | absent on integration | PR-D correction contract test | PR-D required | — | inverted-fk | written, unverified | explicit skip | scaffolded; reproduced only on pinned V2 |
| ISS-05 | Replacement points at predecessor | absent on integration | PR-D correction contract test | PR-D required | — | — | written, unverified | explicit skip | scaffolded; reproduced only on pinned V2 |
| ISS-06 | Active-only projection | absent on integration | PR-D correction contract test | PR-D required | — | inactive-in-projection | written, unverified | explicit skip | scaffolded; reproduced only on pinned V2 |
| ISS-07 | Replay / no identity churn | absent on main | second rebuild ID stability | — | — | — | written, unverified | this PR | reproduced on main |
| ISS-08 | Branch closing through governor | V2 only | `test_non_addressing_evidence_cannot_close_branch` | — | E2E-01 | — | written, unverified | skip | scaffolded |
| ISS-09 | Concurrency / source-event identity persisted | absent on integration | PG concurrent-writer definition | PR-C required | — | — | written, unverified | unconditional skip; no harness | scaffolded |
| E2E-01 | Burning feet + normal EMG | conversation only | — | — | not started | — | not started | | not started |
| E2E-02 | Gallbladder + unrelated EMG | conversation only | safety tests on main | — | not started | — | not started | | not started |
| E2E-07 | Safety escalation persists | `safety_json` on main | `test_safety_nuance` | API | not started | — | locally verified (unit) | a1e82f1 | reproduced on main |
| RL-01 | Required CI green including persist | CI now targets `integration/agent`; persist tests xfail-strict | — | — | — | — | written, unverified | `.github/workflows/ci.yml` | scaffolded |

No item has been skipped to complete. Nothing is CI verified for the truth
layer. Production SHA, runtime flags, and migration state are unknown.
Persistent UAT SHA at last verified check: `843dd55c715b`.
PR-A merge onto `integration/agent`: `6714a08389d8392ef2d4439362cbb4da1e35283a`.
Closeout branch point after PR #34: `7a815069451bf65f32246b8a711f35063c623d39`.
Closeout evidence commit: `1b619482a76add4d89384d573d02c55a896e8250`.
Reviewed Grok PR-A predecessor: `d048fe855fe2179ec16f757ba065c07f96d78ec2`.
Repaired Codex PR-A evidence commit:
`2590b1af20936bd1cec369478fa7d659a8a1a8c0`.
Required CI remained red at merge (inherited catalog/scenario failures). That
redness was not repaired in PR-A and is not evidence that the red-test packet
failed.

## PR-55 increment (2026-08-18)

Candidate SHA `47a3c9d4db738e8e6e9933d3322874b61459496a`. Verdict: **NOT READY**.
See `docs/release/MVP_RELEASE_CANDIDATE.md`.

| Packet | Primary tests | Local result |
|---|---|---|
| PR-48 | `tests/discovery_mvp/test_coverage_ontology.py` | passed |
| PR-49 | `tests/discovery_mvp/test_ranker.py` | passed |
| PR-50 | `tests/discovery_mvp/test_scientific_fail_closed.py` | passed |
| PR-51 | `tests/discovery_mvp/test_intervention_monitoring.py` | passed |
| PR-52 | `tests/test_api/test_discovery_idor.py` | passed |
| PR-53 | `tests/discovery_mvp/test_observability.py` | passed |
| PR-54 | `tests/test_api/test_founder_uat_scenario.py` | passed |
| Exact-SHA `gates` / `postgres-truth` | GitHub Actions | blocked by billing |
| Founder browser UAT | `docs/release/FOUNDER_UAT.md` | unsigned |
