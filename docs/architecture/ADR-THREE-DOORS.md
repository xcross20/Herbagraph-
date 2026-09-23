# ADR: Three doors, one Case

**Status:** accepted for implementation  
**Date:** 2026-09-22  
**PR:** M01 growth quarantine (`grok/hg-m01-growth-quarantine`)

## Context

HerbaGraph has a lab reasoning pipeline, a Guided Discovery / Ask surface for multi-system unexplained concerns, and a planned metabolic Stack Check. Auto-generated PMID rows were merged into `TIER_A_EVIDENCE_CLAIMS`, so growth literature could author recommendation cards.

## Decision

1. **Labs door** — only the lab engine writes normalized biomarkers.
2. **Stack Check door** — grades a stated supplement list against labs + safety. Not a diagnosis.
3. **Ask door** — longitudinal investigation of a concern (neuropathy-like, biliary-like, overlapping systems). The Case is the source of truth. Ask must not become a free-text supplement recommender.

Growth claims (`generated_pmid_claims.py` / `pmid_growth_batch.py`) are `source_layer=growth` and `recommendation_intent=context_only`. They cannot create discuss cards.

## Consequences

- Ask remains the product for niche, overlapping, unanswered cases.
- Stack Check is a separate door, later wired onto the same Case.
- Daily PMID growth (#71) may continue harvesting papers; it may not promote them to PRIMARY without a human/promotion step.
