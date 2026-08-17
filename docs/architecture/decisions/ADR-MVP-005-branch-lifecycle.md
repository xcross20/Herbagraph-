# ADR-MVP-005: Branch lifecycle

**Status:** Proposed (revised 2026-08-17 after PR-A review)  
**Date:** 2026-08-17  
**Owner approval:** required before any close/reopen is user-visible

## Context

Reviewed V2 could only OPEN/REOPEN branches. Close was never routed through `validate_branch_resolution`, so “EMG cannot close small-fiber” was vacuously true.

The first draft listed alternatives inside the decision (`evaluated_open` or `supported-for-further-investigation`; `conditionally_resolved`/`closed`). Persisted vocabulary must be exact.

## Decision

The only persisted branch statuses are:

| Status | Meaning |
| --- | --- |
| `not_evaluated` | Branch is open; no applicable evidence has been applied. |
| `partially_evaluated` | Some applicable evidence exists; it is insufficient to close. |
| `evaluated_open` | Applicable evidence has been applied; the branch remains open for further investigation. |
| `closed` | Governor accepted a close. `resolved_at` may be set only here. |
| `reopened` | A previously closed branch was reopened by an explicit new finding or evidence rule. |

No aliases. `supported-for-further-investigation` and `conditionally_resolved` are not stored values.

### Governor

All close requests pass one lifecycle governor. A test that does not directly assess a branch cannot close it and cannot set `resolved_at`.

Partial evidence cannot be rendered as resolved. Reopen requires an explicit new finding or evidence rule. Transitions record reason, triggering evidence, rule version, and time.

Legal transitions:

| From | To |
| --- | --- |
| `not_evaluated` | `partially_evaluated`, `evaluated_open`, `closed` |
| `partially_evaluated` | `evaluated_open`, `closed` |
| `evaluated_open` | `partially_evaluated`, `closed` |
| `closed` | `reopened` |
| `reopened` | `partially_evaluated`, `evaluated_open`, `closed` |

## Alternatives

- Infer close from any normal test. Rejected: coverage-unaware.
- Leave close unimplemented. Rejected: the gold case requires an explicit open/partial state, not a missing transition.
- Persist `conditionally_resolved` as a sixth status. Rejected: one `closed` value; conditions live in transition metadata.

## Consequences

- No direct status writes outside the governor.
- Map must distinguish `not_evaluated`, `partially_evaluated`, `evaluated_open`, `closed`, and `reopened`.

## Rollback

Governor unused while V2 flags are off.
