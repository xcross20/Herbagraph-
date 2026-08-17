# ADR-MVP-003: Mutation identity and idempotency

**Status:** Proposed  
**Date:** 2026-08-17  
**Owner approval:** required before uniqueness constraints in production

## Context

Reviewed persist appended equivalent findings, gaps, workup, interpretations, timeline events, and evidence on every turn because identity depended on a `source_turn_id` that was never written.

## Decision

Every mutation has a deterministic identity. A replay returns the same semantic state.

| Entity | Identity |
| --- | --- |
| Finding | case + name + value + active |
| Open branch | case + branch code |
| Open gap | case + gap code |
| Workup | case + raw/canonical test + result state |
| Evidence edge | branch + relationship + rationale/source |
| Interpretation | case + statement + active |
| Timeline event | case + label + active |

Database unique constraints must match models. Upsert or conflict handling is required; read-then-insert is not sufficient under concurrency.

## Alternatives

- Dedup only in Python. Rejected: two workers can both insert.
- Depend on `source_turn_id` without persisting it. Rejected: already failed in review.

## Consequences

- Migrations that add unique indexes need a duplicate audit first.
- Turn processing must be transactional.

## Rollback

Constraints are additive. If they cannot be applied to populated data, keep flags off and do not enforce in production.
