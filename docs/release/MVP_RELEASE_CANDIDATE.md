# MVP release candidate (PR-55)

**Verdict: NOT READY**

A successful local walkthrough and a production deploy do not substitute for exact-SHA integrity, scientific, security, and reliability evidence.

## Candidate coordinates

| Item | Value |
|---|---|
| Release SHA | `47a3c9d4db738e8e6e9933d3322874b61459496a` |
| Alembic head | `u6d7e8f9g0h1` |
| Truth-layer flag | user mutations always use the mutation seam; `discovery_truth_layer_authoritative` only authorizes snapshot rebuild writes |
| V2 flags | off / unaccepted |
| Dependency lock | repository `requirements*.txt` |
| UAT branch | `integration/agent` |
| Production project | Railway `91b8f261-38b0-4aa7-b39b-e27c4f8386ee` |

Image/build digest must be copied from the Railway deploy of this SHA. It is not invented here.

## What landed on this SHA (guide packets 48–54)

| Packet | GitHub PR | What it proved locally |
|---|---|---|
| PR-48 coverage/evidence/map | #49 | Versioned catalog, generated notes, no gold-case rule phrases |
| PR-49 ranker | #50 | Persisted gaps, commerce filter, S3/S4 override, no-candidate |
| PR-50 scientific fail-closed | #51 | Invalid statements replaced, citations must resolve |
| PR-51 intervention/monitoring | #52 | Warfarin/herb block, causal taxonomy, idempotent monitoring |
| PR-52 auth/audit | #53 | IDOR 404, Case view audit, PHI-like metric keys rejected |
| PR-53 observability | #54 | Durable metrics file, `x-request-id`, rollback runbook |
| PR-54 founder UAT | #55 | 19-step API scenario; browser UAT script written |

## Traceability (honest)

| Claim | Evidence | Status |
|---|---|---|
| Idempotent replay / append-only | local pytest + prior truth-layer tests | locally green; CI not proven on this SHA |
| Reproducible maps | coverage ontology tests | locally green |
| No diagnosis / fail-closed science | scientific fail-closed + gold tests | locally green |
| Unknown coverage is not negative | coverage + biliary EMG tests | locally green |
| Owner isolation | `test_discovery_idor.py` | locally green |
| Empty PostgreSQL upgrade | alembic head `u6d7e8f9g0h1` | not re-proven on this SHA because Actions billing fails |
| Persistent Railway browser UAT | Founder script only | unsigned |
| Independent security review | threat model drafted | unresolved |
| Human scientific evaluation | not run | unresolved |
| Parser 100-fixture benchmark | still a small generated set | unresolved |
| p95 latency / restore time | documented as unmeasured | unresolved |

## Known limitations and non-goals

- GitHub Actions is failing in seconds because account payments failed. This packet does **not** claim green `gates` or `postgres-truth`.
- Founder has not signed persistent UAT.
- V2 investigation-state remains unaccepted.
- No live EHR/FHIR, wearables, automated N-of-1 causal estimates, or commercial COA integrations.
- Parser evaluation is not yet a reliability benchmark.
- Billing, malware scanning, and signed upload URLs remain incomplete.

## Launch stages (do not skip)

1. Restore GitHub billing and get exact-SHA `gates` + `postgres-truth` green.
2. Dark verification on production with behavior flags unchanged.
3. Founder-supervised UAT on `integration/agent` with the 19-step script.
4. Smallest agreed real-user cohort only after Founder records risk acceptance.
5. Hold and observe. No feature expansion in the watch window.

## Commands

```bash
python3 -m pytest tests/discovery_mvp tests/test_api/test_discovery_gold_boundaries.py tests/test_api/test_discovery_idor.py tests/test_api/test_founder_uat_scenario.py
python3 scripts/validate_coverage_catalog.py
python3 scripts/preflight_migrate.py
# After billing is restored:
# GitHub Actions jobs `gates` and `postgres-truth` on this exact SHA
```

Rollback: `docs/release/ROLLBACK.md`. Migration: `docs/release/MIGRATION_RUNBOOK.md`.

## Why this is not MVP READY

The reliability gate requires exact-SHA CI green, persistent UAT E2E green, and measured rollback/restore. Those are missing. The scientific and authorization work on this SHA is locally demonstrated, not independently certified.

**CONDITIONAL MVP** would require an explicit Founder risk acceptance that names the unpaid CI, unsigned browser UAT, and missing human reviews. That acceptance is not recorded here.
