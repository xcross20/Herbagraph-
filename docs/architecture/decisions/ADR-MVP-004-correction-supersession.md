# ADR-MVP-004: Correction and supersession model

**Status:** Proposed  
**Date:** 2026-08-17  
**Owner approval:** required before canonical-read switch

## Context

Reviewed correction rows pointed `original_claim_id` at the replacement. `supersedes_finding_id` was set on the prior row. Live `batch_from_turn` did not emit supersession. Rebuild then copied inactive V2 findings back into the snapshot.

## Decision

- Resolve or create the true original claim/finding first.
- Mark it inactive or superseded with audit metadata. Do not delete it.
- Create the replacement and set `replacement.supersedes_finding_id = original.id`.
- Correction FKs: `original_claim_id` → original, `replacement_claim_id` → replacement.
- Live turn reconciliation must emit `SupersedeMutation` when a correction replaces an active finding.
- Active projection, prompts, map, and reports use only active rows.
- Ambiguous corrections request clarification rather than guessing.

Reversal is out of scope for MVP; a later correction may supersede the replacement.

## Alternatives

- Overwrite the value in place. Rejected: destroys audit.
- Delete the old row. Rejected: history is the product.

## Consequences

- `apply_snapshot` cannot remain the writer of finding truth.
- History/audit views need an explicit inactive query path.

## Rollback

Flags off. Legacy snapshot path unchanged.
