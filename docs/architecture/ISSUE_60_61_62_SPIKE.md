# Issues 60–62 spike (MVP scope limit)

Inspected existing coverage catalog, ranker, literature seam, audit, and `control_json`. No V2 flags activated.

## #60 composition

Reuse versioned JSON identity layers (`concept → subtype → phenotype → part → form → preparation → product/batch → exposure → measured composition → claim`). B12, biotin, grapes, and culinary salts are calibration fixtures, not domain tables. Inheritance of measured values or outcomes is forbidden.

Boundary: #60 owns identity. It is not the investigation planner.

## #61 modalities

Extend the existing coverage catalog with modality metadata and **three** complete synthetic maps (burning feet, RUQ, facial heat). Labs are one modality. EMG remains `does_not_directly_assess` small-fiber density.

## #58 Slice B/C

`next_evidence.plan_next_evidence` ranks eligible multimodal candidates from active (not paused) concerns through the existing ranker. Claim cards resolve only to stored fixture sources (`pmc:` / FDA URLs). No invented PMIDs.

## #62 decision events

`decision_events.record_decision` snapshots the candidate set after ranking. Replay of the same source event is idempotent. Events never change scientific rank. Consent purpose defaults to `direct_service`. Instrumentation failure must not block Ask.

## #60 configuration-only fifth domain

`composition_graph_extensibility_folate.json` is the MVP proof that another nutrient can reuse the same layers. It is not a catalog expansion.

## #62 later evidence

`link_later_evidence` computes a governed map delta. Recalled total B12 is `partially_assessed` and cannot close. Non-addressing coverage stays `non_addressing`. `founder_uat_view` is metrics-only.

## Not in this increment

Exhaustive food/nutrient catalogs, outcome-trained ranking, production flag activation, or replacing the lab engine.
