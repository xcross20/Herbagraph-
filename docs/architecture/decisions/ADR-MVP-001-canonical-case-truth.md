# ADR-MVP-001: Canonical case truth

**Status:** Proposed  
**Date:** 2026-08-17  
**Owner approval:** required before production enablement

## Context

`main` rebuilds Discovery by deleting and recreating `DiscoveryFinding` and `DiscoveryHypothesis` rows (`apply_snapshot`). That makes the snapshot the writable truth. The master spec requires a longitudinal Case graph whose projection cannot resurrect or invent facts.

## Decision

Normalized investigation-graph entities (findings, branches, gaps, workup, evidence, corrections, timeline, interpretations) are the canonical source of truth. The legacy case snapshot is a derived compatibility projection only. Projection rebuild must be deterministic, idempotent, and read-only with respect to canonical rows.

## Alternatives

- Keep snapshot-as-truth and add more columns to the snapshot JSON. Rejected: corrections and inactive history cannot be represented safely.
- Dual-write forever without a canonical read path. Rejected: two truths will diverge.

## Consequences

- Rebuild may not delete canonical history.
- Inactive rows stay queryable for audit and stay out of active prompts, maps, and reports.
- Enabling this path is a one-way door for persisted data and requires Founder approval plus a later migration plan.

## Rollback

Leave feature flags off. Old code continues to read/write the snapshot. Do not add uniqueness constraints to populated production until a dry-run audit passes.

## Invariants

- One current active representation per applicable identity.
- Historical rows cannot re-enter the active projection.
- Projection failure cannot mutate canonical state.
