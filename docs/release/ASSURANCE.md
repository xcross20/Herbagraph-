# Discovery Engine independent assurance

This is not a substitute for Issue #37. It is the layer that should have blocked PR #36.

## 1. Technical merge gates

Workflow `.github/workflows/merge-gates.yml` fails unless:

- `gates` and `postgres-truth` are success on the PR head SHA;
- an exact-SHA `HERBAGRAPH_ARCHITECT_REVIEW` with `Status: ARCHITECT_APPROVED` exists;
- no `CHANGES_REQUESTED` / `CHANGES_REQUIRED` remains on that SHA.

Founder must require those checks on `integration/agent` and disable administrator bypass except the documented emergency comment:

```text
HERBAGRAPH_EMERGENCY_BYPASS
Commit: <40-char SHA>
Reason: ...
```

Human instructions alone are not sufficient. Do not use `gh pr merge --admin` except that recorded emergency.

## 2. Required PostgreSQL

Job `postgres-truth` runs empty-db migration, upgrade/downgrade rehearsal, two-session replay, and live constraint inspection. `HERBAGRAPH_REQUIRE_POSTGRES=1` turns skips into failures.

## 3. Property sequences

`tests/discovery_mvp/test_property_sequences.py` generates correction/replay/rebuild/close-attempt sequences and asserts one active fact, no resurrection, no missing predecessor, and no close on non-addressing EMG.

## 4. Boundary gold cases

`tests/test_api/test_discovery_gold_boundaries.py` is the Ask/API path. Helper interpret_workup tests are component tests only.

## 5. Scientific benchmark

`benchmarks/scientific/v1/cases.json` is sourced from the master spec, not from current model output. `app/discovery/scientific_benchmark.py` grades entailment, provenance, coverage, and commerce neutrality.

## 6. Dark launch

`discovery_truth_layer_authoritative` defaults false. Compare old vs new projections before enabling writes. UAT remains test-only.

## 7–8. Tripwires and failure injection

`app/discovery/tripwires.py` and `tests/discovery_mvp/test_failure_injection.py`. Counters are PHI-safe names only.

## 9. Independent human review

See `docs/release/INDEPENDENT_REVIEW.md`. Not replaceable by CI.

## Order

1. Merge Issue #37 (PR #38) after exact-SHA architect approval.
2. Require merge-gates + postgres-truth on `integration/agent`.
3. Keep catalog CI green.
4. Expand property and gold corpora.
5. Dark-launch compare, then founder/expert UAT.
