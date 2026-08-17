# Milestone 0 baseline

**Recorded:** 2026-08-17  
**Recorder:** Grok Implementer  
**Working branch:** `agent/mvp-baseline-repair`, carrying PR-A from `integration/agent`
**Spec:** `docs/architecture/HERBAGRAPH_DISCOVERY_ENGINE_MASTER_SPEC.md`

## Commits

| Ref | SHA |
| --- | --- |
| `origin/main` | `88c145bf64cea16014a705217597e6efdc962a44` |
| `origin/integration/agent` | `7132b5121d20cb749b6208419f154374e0c040e6` |
| Reviewed Grok PR-A predecessor | `d048fe855fe2179ec16f757ba065c07f96d78ec2` |
| Repaired Codex PR-A evidence commit | `2590b1af20936bd1cec369478fa7d659a8a1a8c0` |
| `origin/agent/architecture-foundation` (PR #5) | `681a24f504c7fea7aafbef9822d3a0c88e3b9cf1` |
| `origin/discovery/investigation-state-v2` | `e7ab37aeed5538546fd657a6b0c1a394ad937510`; unexpectedly merged to `main` by PR #4 |
| Production deploy SHA | **unknown** — Railway production still sourced from `claude/herbagraph-test-suite-mgmrz1`; no confirmed SHA |
| Persistent UAT deploy SHA | `843dd55c715b` — `https://herbagraph-uat.up.railway.app/meta` after merge to `integration/agent` |

“Same lineage as main” is not a deploy identity. Do not treat production as `cd42abf`.

PR #4 merged the previously forensic V2 branch into `main` at `88c145b`
without the PR-A → PR-B–E acceptance sequence. That merge does not convert the
V2 behavior into an accepted contract. The incident hold remains authoritative:
do not activate its flags, apply its migration, or build follow-on behavior on
the merge until containment is resolved. `integration/agent` intentionally does
not contain PR #4 and advanced independently through PR #18.

## Migration head

On `integration/agent`: `t0u1v2w3x4y5` (`safety_json` only).

On current `main` after PR #4: source includes `u1v2w3x4y5z6`
(investigation graph + coverage tables). Whether it was applied to any runtime
database remains **unknown**. Source presence is not migration/deployment proof.

## Feature flags

Current `main` contains the V2 settings from PR #4. Their code defaults are
**false** (`discovery_investigation_state_v2`,
`discovery_append_only_findings`, `discovery_coverage_graph_enabled`,
`discovery_document_reconciliation`, `discovery_voice_enabled`,
`discovery_intervention_ledger`). Runtime overrides remain **unknown**.

Do not infer that production is on either the legacy or V2 path until its exact
deploy SHA, flag values, and migration state are independently verified.

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

## Entity inventory on the approved integration base

Present: `DiscoveryCase`, `DiscoveryFinding`, `DiscoveryHypothesis`, `DiscoveryOutcome`, `DiscoveryTurn`, `DiscoveryMapVersion`, `DiscoveryTestPlanItem`, `DiscoveryLongitudinalSnapshot`.

Absent on `integration/agent`: timeline events, patient interpretations,
investigation branches, branch evidence, evidence gaps, prior-workup table,
evidence events, reasoning claims/corrections, coverage ontology tables.

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

Reviewed files (`branch_service.py`, `mutations.py`, `reconciliation.py`,
`epistemics.py`, `app/coverage/`) **do not exist on the approved integration
base**. They now exist on `main` only because of the unaccepted PR #4 merge.
Stop condition from Section 16 remains active for implementation targeting
`integration/agent`.

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
