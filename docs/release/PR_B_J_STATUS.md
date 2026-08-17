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
| PR-J Reliability | **open** | Forward migration exists. Required catalog CI was inherited-red; this packet also repairs scenario `normal`/`optimal` matching, CRP lab-range expectation, and `liver_disease` library key so required gates can go green. Observability tripwires remain thin. |

These packets are not founder-accepted complete. Do not promote to `main` or production on this report.
