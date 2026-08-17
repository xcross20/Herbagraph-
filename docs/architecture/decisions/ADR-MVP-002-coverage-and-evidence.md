# ADR-MVP-002: Coverage and evidence semantics

**Status:** Proposed
**Date:** 2026-08-17
**Owner approval:** required before production enablement

## Context

Reviewed V2 persist mixed coverage strings (`does_not_directly_assess`) with evidence enums (`does_not_address`) and converted `not_applicable` into `inconclusive`, attaching unmatched tests to unrelated branches.

## Decision

Coverage and evidence are different types. One pure mapping function is the only conversion boundary.

Coverage: `directly_assesses`, `partially_assesses`, `does_not_directly_assess`, `not_applicable`, `unknown`.

Evidence: `supports`, `weakens`, `does_not_address`, `resolves_gap`, `inconclusive`.

Mapping:

- `not_applicable` or `unknown` → no evidence edge
- `does_not_directly_assess` → `does_not_address`
- `partially_assesses` → branch rule may choose `inconclusive` / `supports` / `weakens`; never closes alone
- `directly_assesses` + result → branch-specific rule; never a generic positive/negative across all tests

## Alternatives

- Single shared enum. Rejected: strings look related and were assigned interchangeably.
- Attach unmatched tests as `inconclusive`. Rejected: contaminates unrelated branches.

## Consequences

- Resolvers must return exact, alias, ambiguous, or unresolved — never silent substring defaults (generic `MRI` → brain MRI).
- Map serialization must show non-addressing evidence without treating it as negative or closing.

## Rollback

Mapping lives behind unused V2 flags until Architect/Founder approval. No production read path depends on it yet.
