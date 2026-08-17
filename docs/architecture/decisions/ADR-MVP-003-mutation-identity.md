# ADR-MVP-003: Mutation identity and idempotency

**Status:** Proposed (revised 2026-08-17 after PR-A review)  
**Date:** 2026-08-17  
**Owner approval:** required before uniqueness constraints in production

## Context

Reviewed persist appended equivalent findings, gaps, workup, interpretations, timeline events, and evidence on every turn because identity depended on a `source_turn_id` that was never written.

The first draft of this ADR put mutable `active` flags and rationale text into identity keys. That is unsafe: flipping `active` would change identity, collapsing or duplicating rows; rationale edits would fork evidence; same-label timeline events would overwrite repeated legitimate occurrences.

## Decision

Every mutation has a deterministic identity. A replay of the same source event returns the same semantic state. **Identity does not include mutable lifecycle flags.**

| Entity | Identity |
| --- | --- |
| Finding | case + normalized concept + normalized value + source event/turn |
| Open branch | case + branch code |
| Gap event identity | case + branch + gap code + source event/turn |
| Workup | case + canonical test + occurrence/date + normalized result |
| Evidence edge | case + branch + workup/source + relationship + version |
| Interpretation | case + normalized statement + provenance + version |
| Timeline event | case + event type + source event/turn |
| Monitoring event | case + target + observation time + source event |

### Identity versus active uniqueness

- **Identity** answers “is this the same mutation/event?” It is immutable once written.
- **Active uniqueness** answers “is there at most one current representation?” Enforce a PostgreSQL partial unique index on `(case_id, branch_id, code)` for open/active rows separately from immutable event identity.
- Do not put `active` or another mutable lifecycle value into any semantic identity. A closed historical gap and a later reopened gap remain distinct through their source event/turn while the partial index permits only one current open gap for a branch and code.

This branch-scoped rule is the precise form of the master specification's
section 21.5 invariant. The earlier section 5 candidate identity
(`case + gap code + active state`) is not implementable as written because it
omits `branch_id` and treats mutable state as identity. No database constraint
may be implemented until the Founder accepts this resolution.

### Concurrency

Database unique constraints must match models. Upsert or `ON CONFLICT` is required; read-then-insert is not sufficient under two concurrent writers. SQLite tests cannot substantiate this claim.

Every command/event carries an idempotency key or this deterministic identity.

## Alternatives

- Dedup only in Python. Rejected: two workers can both insert.
- Depend on `source_turn_id` without persisting it. Rejected: already failed in review.
- Include `active` or rationale text in finding/evidence identity. Rejected: mutable fields are not identity.

## Consequences

- Migrations that add unique indexes need a duplicate audit first.
- Turn processing must be transactional.
- Repeated legitimate workups and timeline events remain distinct because occurrence/date or source event is part of identity.

## Rollback

Constraints are additive. If they cannot be applied to populated data, keep flags off and do not enforce in production.
