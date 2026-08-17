# Milestone 0 baseline

**Recorded:** 2026-08-17  
**Recorder:** Grok Implementer  
**Working branch:** `grok/mvp-baseline-red-tests` from `integration/agent`  
**Spec:** `docs/architecture/HERBAGRAPH_DISCOVERY_ENGINE_MASTER_SPEC.md`

## Commits

| Ref | SHA |
| --- | --- |
| `origin/main` | `cd42abfa8eb794110e20fe1a7ba1c35b2f8644bd` |
| `origin/integration/agent` | `843dd55c715b4098b4661ca1acede2f5578674e7` |
| This PR-A head after rebase | `d62b9b7a53d179ddbcf60ab8a56b5fbea55c9fa5` |
| `origin/agent/architecture-foundation` (PR #5) | `681a24f504c7fea7aafbef9822d3a0c88e3b9cf1` |
| `origin/discovery/investigation-state-v2` (forensic only) | `e7ab37aeed5538546fd657a6b0c1a394ad937510` |
| Production deploy SHA | **unknown** — Railway production still sourced from `claude/herbagraph-test-suite-mgmrz1`; no confirmed SHA |
| Persistent UAT deploy SHA | `843dd55c715b` — `https://herbagraph-uat.up.railway.app/meta` after merge to `integration/agent` |

“Same lineage as main” is not a deploy identity. Do not treat production as `cd42abf`.

`integration/agent` is ahead of `main` (UAT app + canary merge). The V2 branch is forensic/reference material only. Do not merge it wholesale.

## Migration head

On `main` / `integration/agent`: `t0u1v2w3x4y5` (`safety_json` only).

On `discovery/investigation-state-v2`: additional unreleased revision `u1v2w3x4y5z6` (investigation graph + coverage tables). **Not applied in production.**

## Feature flags

On `main`: no `discovery_investigation_state_v2` setting exists.

On V2 branch: all Discovery V2 flags default **false** (`discovery_investigation_state_v2`, `discovery_append_only_findings`, `discovery_coverage_graph_enabled`, `discovery_document_reconciliation`, `discovery_voice_enabled`, `discovery_intervention_ledger`).

Production is therefore on the legacy snapshot rebuild path.

## CI

`.github/workflows/ci.yml` (after this PR-A revision) runs `bash scripts/ci_gates.sh` on push/PR to `main`, `master`, `claude/**`, and `integration/agent`.

`scripts/ci_gates.sh` is mandatory and ends with `python3 -m pytest tests/` as a blocking step. The later “Upload coverage” job step is the only `continue-on-error` pytest invocation.

Known red tests in `tests/discovery_mvp/` use `pytest.mark.xfail(strict=True)`. An unexpected pass fails CI. Scaffolded contract tests skip. Remove the xfail marker only when the implementation lands.

## Existing test run

Initial packet (subset, 2026-08-17):

```text
command: .venv/bin/python -m pytest tests/test_discovery tests/test_api/test_discovery_layer.py tests/test_api/test_discovery_cases.py tests/test_frontend/test_portals.py tests/test_alembic_env.py -q --tb=no
result: 110 passed in 1.45s
cwd: herbagraph @ a1e82f1
```

Required command (full suite, this revision):

```text
command: .venv/bin/python -m pytest tests/ -q --tb=line
```

Exact result is recorded in `RED_FIRST_LOG.md` for this revision.

This suite does **not** prove persist identity, coverage edges, correction links, or concurrency until the xfailed red tests are implemented and the markers removed.

PostgreSQL uniqueness/concurrency tests are defined in `tests/discovery_mvp/test_postgres_integrity.py` and skip on SQLite. Spec layer B remains unverified.

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

Issues 1–9 from the V2 review are **not reproduced on this branch**. They are labeled:

| Claim label | Meaning |
| --- | --- |
| `reproduced on main` | A failing (xfail-strict) test against `apply_snapshot` / public certainty surfaces that exist here |
| `scaffolded` | Contract or persist-path test whose modules are absent; skip, not a reproduction |
| `reproduced on pinned V2 branch` | Forensic only, SHA `e7ab37aeed5538546fd657a6b0c1a394ad937510` |

On `main`, the live defect is the destructive snapshot rebuild plus public diagnostic-certainty fields. Do not merge `discovery/investigation-state-v2`. After PR-A, port useful V2 work in PR-B through PR-E order from a fresh `integration/agent` branch.

## External dependencies (no secret values)

- PostgreSQL (`DATABASE_URL`)
- Redis (worker)
- LLM provider key (`OPENAI_API_KEY` or MiniMax)
- Supabase JWT when `AUTH_PROVIDER=supabase`
- NCBI / PubMed (`NCBI_API_KEY`, `NCBI_EMAIL`)
- Railway project `charming-charisma` for production deploy

## Trap line

Passing the 110 Discovery unit/API tests does not demonstrate that live persistence, projection, API, or user-visible paths preserve truth after retry, correction, or return visit.
