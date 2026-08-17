# ADR-MVP-005: Branch lifecycle

**Status:** Proposed  
**Date:** 2026-08-17  
**Owner approval:** required before any close/reopen is user-visible

## Context

Reviewed V2 could only OPEN/REOPEN branches. Close was never routed through `validate_branch_resolution`, so “EMG cannot close small-fiber” was vacuously true.

## Decision

Legal statuses: `not_evaluated`, `partially_evaluated`, `evaluated_open` (or supported-for-further-investigation), `conditionally_resolved`/`closed`, `reopened`.

All close requests pass one lifecycle governor. A test that does not directly assess a branch cannot close it and cannot set `resolved_at`.

Partial evidence cannot be rendered as resolved. Reopen requires an explicit new finding or evidence rule. Transitions record reason, triggering evidence, rule version, and time.

## Alternatives

- Infer close from any normal test. Rejected: coverage-unaware.
- Leave close unimplemented. Rejected: the gold case requires an explicit open/partial state, not a missing transition.

## Consequences

- No direct status writes outside the governor.
- Map must distinguish open, partial, closed, and reopened.

## Rollback

Governor unused while V2 flags are off.
