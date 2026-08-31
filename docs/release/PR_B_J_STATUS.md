# PR-B through PR-J status after Issue #37 remediation

Status vocabulary: passed | partial | scaffolded | open

| Packet | Status | Evidence |
| --- | --- | --- |
| PR-B Coverage/evidence | **partial** | Mapping seam, resolver, persist-path attach, UNKNOWN vs explicit NOT_APPLICABLE. Not yet the only Ask-turn write path. |
| PR-C Identity/uniqueness | **partial** | Identity keys, unique index, IntegrityError savepoint recovery. Two-session PostgreSQL test runs when `HERBAGRAPH_TEST_POSTGRES` is set; skipped locally without Postgres. |
| PR-D Corrections/projection | **partial** | All-inactive projection no longer resurrects snapshot A. A→B→A is append-only. Ask still rebuilds hypotheses destructively. |
| PR-E Lifecycle/gaps | **partial** | Governor component tests pass. Not wired as the only Ask close path. Active-gap unique index added in `u2v3w4x5y6z8`. |
| PR-F Scientific output | **scaffolded** | Validator is callable. Certainty keys omitted from map/API/UI. Not an enforced report gate. |
| PR-G Ranker | **scaffolded** | Deterministic ranker with safety override. Not the live Ask selector. |
| PR-H Monitoring | **partial** | Persist + API `/monitoring`. Causation notes rejected. Not a full intervention ledger. |
| PR-I E2E | **partial** | Helper traces reclassified as component tests. API gold cases cover create/document/get/map/return-visit/monitoring. Parser benchmark not added. |
| PR-J Reliability | **passed** | All 12 ci_gates.sh gates pass (ruff, pathway coverage, alias resolution, evidence gaps, PMID integrity, lab scenarios, scenario coverage, seed counts, sample labs, unresolved abnormal audit, pipeline resilience, pytest). Six unwired tripwire counters wired: `paused_concern_selected`, `semantic_repeat`, `commerce_changed_scientific_rank`, `unknown_coverage_as_negative`, `sourceless_scientific_output`, `safety_escalation_lost`. F401 unused import in test_usefulness_certification.py fixed. Full suite: 1839 passed, 8 skipped. |

These packets are not founder-accepted complete. Do not promote to `main` or production on this report.
