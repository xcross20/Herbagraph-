# Milestone 0 baseline

**Recorded:** 2026-08-17  
**Recorder:** Grok Implementer  
**Working branch:** `grok/mvp-baseline-red-tests` from `integration/agent`  
**Spec:** `docs/architecture/HERBAGRAPH_DISCOVERY_ENGINE_MASTER_SPEC.md`

## Commits

| Ref | SHA |
| --- | --- |
| `origin/main` | `a1e82f15b7ef318e77b20c3809343e98497ac2ba` |
| `origin/integration/agent` | `a1e82f15b7ef318e77b20c3809343e98497ac2ba` |
| `origin/agent/architecture-foundation` (PR #5) | `681a24f504c7fea7aafbef9822d3a0c88e3b9cf1` |
| `origin/discovery/investigation-state-v2` | `e7ab37aeed5538546fd657a6b0c1a394ad937510` |
| Production (`www.herbagraph.com` last confirmed deploy) | same lineage as `main` through GI-questioning fix; V2 not deployed |

`integration/agent` currently equals `main`. No autonomous work has been merged into the staging lane yet.

## Migration head

On `main` / `integration/agent`: `t0u1v2w3x4y5` (`safety_json` only).

On `discovery/investigation-state-v2`: additional unreleased revision `u1v2w3x4y5z6` (investigation graph + coverage tables). **Not applied in production.**

## Feature flags

On `main`: no `discovery_investigation_state_v2` setting exists.

On V2 branch: all Discovery V2 flags default **false** (`discovery_investigation_state_v2`, `discovery_append_only_findings`, `discovery_coverage_graph_enabled`, `discovery_document_reconciliation`, `discovery_voice_enabled`, `discovery_intervention_ledger`).

Production is therefore on the legacy snapshot rebuild path.

## CI

`.github/workflows/ci.yml` runs `bash scripts/ci_gates.sh` on push/PR to `main`/`master`/`claude/**` only. It does **not** trigger on `integration/agent` or `grok/**`.

`ci_gates.sh` is catalog/reseed/PMID/scenario audits, not the Discovery persist suite.

Pytest is optional/non-blocking in CI (`continue-on-error: true`).

## Existing test run (unmodified)

```text
command: .venv/bin/python -m pytest tests/test_discovery tests/test_api/test_discovery_layer.py tests/test_api/test_discovery_cases.py tests/test_frontend/test_portals.py tests/test_alembic_env.py -q --tb=no
result: 110 passed in 1.45s
cwd: herbagraph @ a1e82f1
```

This suite does **not** prove persist identity, coverage edges, correction links, or concurrency.

PostgreSQL uniqueness/concurrency tests were not run in this packet (local default test DB is SQLite). Spec layer B remains unverified.

## Entity inventory on `main`

Present: `DiscoveryCase`, `DiscoveryFinding`, `DiscoveryHypothesis`, `DiscoveryOutcome`, `DiscoveryTurn`, `DiscoveryMapVersion`, `DiscoveryTestPlanItem`, `DiscoveryLongitudinalSnapshot`.

Absent on `main`: timeline events, patient interpretations, investigation branches, branch evidence, evidence gaps, prior-workup table, evidence events, reasoning claims/corrections, coverage ontology tables.

`apply_snapshot` (`app/discovery/service.py`) deletes all findings and hypotheses for the case, then inserts a rebuilt snapshot. That is incompatible with ADR-MVP-001.

## Feature inventory

| Capability | State | Evidence |
| --- | --- | --- |
| Lab parser / staged analysis | reported | existing pipeline + CI scenario gates |
| Biomarker / pathway / evidence / reports | reported | catalog CI + report tests |
| Auth / patients | reported | API auth/patient tests |
| Persistent cases and turns | partial | cases persist; findings are rebuilt destructively |
| Two-pass Discovery Guide | reported | `guide.py` + guide tests |
| Person context / return visit / voice input | reported | Ask UI + recent commits |
| S0–S4 safety | reported | `tests/test_discovery/test_safety_nuance.py` |
| Investigation map as coverage-aware persist | not started on `main` | computed from snapshot; includes `certainty` |
| Append-only investigation graph | broken / off-main | V2 branch exists; flags off; not on `main` |
| Lab → Case evidence bridge | not started | |
| Intervention → monitoring loop | not started | |
| Scientific-output contract | not started | |
| Parser outcome taxonomy (failed vs empty) | unknown | not inventoried this packet |

## Reviewed defect reproduction

Reviewed files (`branch_service.py`, `mutations.py`, `reconciliation.py`, `epistemics.py`, `app/coverage/`) **do not exist on `main`**. Stop condition from Section 16: reviewed files no longer match this branch.

On `origin/discovery/investigation-state-v2` @ `e7ab37a`, persist-invariant tests were added after the review and currently pass there. That is **locally verified on an unmerged branch**, not CI verified, not on `main`, and flags remain off.

On `main`, the live defect is the destructive snapshot rebuild, not the five V2 persist bugs (those modules are absent).

## External dependencies (no secret values)

- PostgreSQL (`DATABASE_URL`)
- Redis (worker)
- LLM provider key (`OPENAI_API_KEY` or MiniMax)
- Supabase JWT when `AUTH_PROVIDER=supabase`
- NCBI / PubMed (`NCBI_API_KEY`, `NCBI_EMAIL`)
- Railway project `charming-charisma` for production deploy

## Trap line

Passing the 110 Discovery unit/API tests does not demonstrate that live persistence, projection, API, or user-visible paths preserve truth after retry, correction, or return visit.
