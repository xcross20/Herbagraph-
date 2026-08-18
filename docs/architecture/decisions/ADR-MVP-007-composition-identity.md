# ADR-MVP-007: Substance, form, assay, and composition identity

**Status:** Accepted for MVP fixtures  
**Date:** 2026-08-18  
**Issues:** #60, #61, #62

## Decision

Identity lives in versioned configuration (`composition_graph_v1.json`). Layers are `concept → subtype → phenotype → part → form → preparation → product_batch → exposure → assay → measured_composition → claim`. A fifth domain is added by overlay JSON that reuses those layers. Python schema does not change.

#60 owns identity. #61 owns modalities and next-evidence ranking. #62 snapshots ranked decisions and later map deltas. The composition graph is not the investigation planner.

## Rules

- Measured values and outcome claims do not inherit across parent/child or batch/category edges.
- An assay may `partially_assess` a parent concept; it cannot close the parent by identity alone.
- Biochemical activity is not clinical superiority.
- Unknown product form stays unknown.
- Commerce, availability, and margin stay off this graph.

## Rollback

Remove the overlay file. The base graph remains. No production migration is required for this packet.
