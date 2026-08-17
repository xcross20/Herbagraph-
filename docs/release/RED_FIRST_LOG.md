# Red-first log — Milestone 1

## Revision 1 (preserved)

**Branch:** `grok/mvp-baseline-red-tests`
**Commit:** `01dad5153866aea4d5fab7512299a56561f40ea3`
**Command:** `.venv/bin/python -m pytest tests/discovery_mvp -q --tb=line`
**Result:** 6 failed, 1 passed in 0.22s
**Date:** 2026-08-17

| Test | Failure | Violated invariant | Intended? |
| --- | --- | --- | --- |
| `test_finding_identity_survives_rebuild` | `assert None is not None` (original finding id gone after `rebuild_case`) | DI-01 / ADR-MVP-001 | yes — `apply_snapshot` deletes rows |
| `test_projection_must_not_use_deleted_history` | original `onset=after surgery` row is `None` after `apply_snapshot` | DI-10 / ADR-MVP-004 | yes — history is destroyed, not inactivated |
| `test_second_rebuild_is_not_a_new_truth` | passed | DI-05 (weak form) | rebuild currently recreates one row from extras; **not** proof of identity stability |
| `test_not_applicable_creates_no_evidence_relationship` | `ModuleNotFoundError: app.discovery.evidence_mapping` | DI-13 / ADR-MVP-002 | import failure, **not** a persist-path reproduction |
| `test_unknown_coverage_creates_no_evidence_relationship` | same import failure | DI-13 | same |
| `test_does_not_directly_assess_maps_to_does_not_address` | same import failure | DI-14 / ADR-MVP-002 | same |
| `test_map_payload_must_not_carry_diagnostic_certainty` | `'certainty' not in` snapshot map payload | SO-02 | yes — but substring would also match `not_disease_probability` |

No production behavior was changed to obtain these failures.

Note: persist Issues 1–9 from the V2 review cannot be reproduced on this branch because those modules are not on `main`/`integration/agent`. They were reproduced and then repaired on `origin/discovery/investigation-state-v2` @ `e7ab37a` (unmerged, flags off). That repair is **not** part of this PR.

## Revision 2 (preserved Grok PR-A correction)

**Why:** Review of revision 1 — weak replay test, correction test did not prove projection, coverage tests failed at import, certainty test was contradictory, CI would break `integration/agent`.

**Mechanism:** `pytest.mark.xfail(strict=True)` for reproduced-on-main defects. Unexpected pass fails CI. Scaffolded tests skip.

**Command (full suite):** `.venv/bin/python -m pytest tests/ -q --tb=line`

```text
47 failed, 1505 passed, 11 skipped, 6 xfailed in 1472.45s
cwd: herbagraph @ grok/mvp-baseline-red-tests (this revision)
```

Discovery MVP packet: 6 xfailed (reproduced on main), 7 skipped (scaffolded). None of the 47 failures are in `tests/discovery_mvp/`. They are pre-existing catalog/scenario/e2e failures on this checkout (nutritional scenario matrix, one normalizer assertion, two LLM e2e JSON failures, one safety condition list). PR-A did not change production code to produce them.

Baseline subset still green:

```text
.venv/bin/python -m pytest tests/test_discovery tests/test_api/test_discovery_layer.py tests/test_api/test_discovery_cases.py tests/test_frontend/test_portals.py tests/test_alembic_env.py tests/discovery_mvp -q --tb=line
110 passed, 7 skipped, 6 xfailed in 1.72s
```

| Test | Claim label | Expected now |
| --- | --- | --- |
| `test_finding_identity_survives_rebuild` | reproduced on main | xfail (AssertionError: row gone) |
| `test_correction_inactivates_original_and_excludes_it_from_projection` | reproduced on main | xfail (row gone; no active/supersedes fields) |
| `test_second_rebuild_is_not_a_new_truth` | reproduced on main | xfail (identity churn; no longer a count-only pass) |
| mapping unit tests | scaffolded | skip (no module) |
| persist-path unrelated evidence | scaffolded | skip |
| branch close | scaffolded | skip |
| map / API / frontend certainty key tests | reproduced on main | xfail |
| PostgreSQL uniqueness / concurrency | scaffolded | skip on SQLite (later made unconditional) |

## Revision 3 (Codex repair branch)

**Source SHA reviewed:** `d048fe855fe2179ec16f757ba065c07f96d78ec2`
**Branch:** `agent/mvp-baseline-repair`
**Exact repaired evidence commit:** `2590b1af20936bd1cec369478fa7d659a8a1a8c0`

The later metadata-only commit that records this SHA changes no tests or
production behavior. Exact-SHA CI remains required before merge.

Review repairs:

- split the reproduced correction-history deletion from the unimplemented
  predecessor-link and active-projection contracts;
- made PostgreSQL definitions unconditional scaffolds until PR-C supplies a
  real migration and concurrent-writer harness;
- aligned branch-scoped gap identity with section 21.5 and kept mutable state
  out of identity;
- refreshed repository state after PR #4 merged to `main` and PR #18 merged to
  `integration/agent`.

Focused packet:

```text
command: /Users/immanuellewis/herbagraph/.venv/bin/python -m pytest tests/discovery_mvp -q --tb=line
result: 8 skipped, 6 xfailed in 0.19s
```

Protocol packet:

```text
command: PYTHONPATH=scripts /Users/immanuellewis/herbagraph/.venv/bin/python -m pytest tests/test_agent_protocol -q --tb=line
result: 61 passed in 0.31s
```

Full suite:

```text
command: /Users/immanuellewis/herbagraph/.venv/bin/python -m pytest tests/ -q --tb=line
result: 45 failed, 1575 passed, 12 skipped, 6 xfailed in 298.35s
```

All 45 failures are outside `tests/discovery_mvp/`: 41 scenario-matrix cases,
the safety-condition inventory, canonical biomarker reference normalization,
the aggregate scenario gate, and the trend-pair gate. Required CI remained red
and merge-blocking. This branch changed no production behavior or catalog data.

## Revision 4 (closeout after PR #33 merge)

**Why:** PR #33 merged the revision-3 repair onto
`integration/agent@6714a08389d8392ef2d4439362cbb4da1e35283a` without an
architect review of that exact SHA. Evidence docs still said "skip on SQLite"
and "do not merge V2" after the tests had become unconditional skips and PR #4
had already merged V2 into `main`.

**Closeout branch point:** `7a815069451bf65f32246b8a711f35063c623d39`

Independent focused packet on this checkout:

```text
command: /Users/immanuellewis/herbagraph/.venv/bin/python -m pytest tests/discovery_mvp -q --tb=line
result: 8 skipped, 6 xfailed in 0.23s
```

| Test | Claim label | Expected now |
| --- | --- | --- |
| `test_finding_identity_survives_rebuild` | reproduced on main | xfail (row gone) |
| `test_correction_preserves_original_history` | reproduced on integration | xfail (row gone; history not preserved) |
| `test_correction_links_replacement_and_excludes_inactive_history_from_all_active_projections` | scaffolded | skip (no linkage/active fields) |
| `test_second_rebuild_is_not_a_new_truth` | reproduced on main | xfail (identity churn) |
| mapping unit tests | scaffolded | skip (no module) |
| persist-path unrelated evidence | scaffolded | skip |
| branch close | scaffolded | skip |
| map / API / frontend certainty key tests | reproduced on main | xfail |
| PostgreSQL uniqueness / concurrency | scaffolded | unconditional skip until PR-C |

Protocol packet:

```text
command: PYTHONPATH=scripts /Users/immanuellewis/herbagraph/.venv/bin/python -m pytest tests/test_agent_protocol -q --tb=line
result: 63 passed in 0.43s
```

Full suite:

```text
command: /Users/immanuellewis/herbagraph/.venv/bin/python -m pytest tests/ -q --tb=line
result: 45 failed, 1577 passed, 12 skipped, 6 xfailed in 457.91s
```

The +2 passed versus the PR #33 record (`1575 passed`) are inherited
`tests/test_agent_protocol` additions from PR #34, not Discovery MVP changes.
All 45 failures are outside `tests/discovery_mvp/`. Required CI is still red
from those inherited catalog/scenario failures. That is outside PR-A.
