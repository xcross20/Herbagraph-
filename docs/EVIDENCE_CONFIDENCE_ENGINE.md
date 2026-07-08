# HerbaGraph Evidence Confidence & Explainability Engine v1.0

The Evidence Confidence Engine explains **why** every recommendation exists, **how confident** HerbaGraph is, **what evidence** supports it, and **what uncertainty** remains. Confidence is **never** invented by the LLM.

## Pipeline position

```
Knowledge Layer
      ↓
Clinical Reasoning (LLM)
      ↓
Evidence Confidence & Explainability Engine   ← this module
      ↓
Safety Engine v1.0
      ↓
Ranking (safety-adjusted confidence)
      ↓
LLM Narrative Generation (intervention_narrative only)
```

## Package layout

| Path | Role |
|------|------|
| `app/evidence_confidence/engine.py` | Main entry: `build_explainability_bundle()` |
| `app/evidence_confidence/scoring.py` | Transparent confidence numeric + level |
| `app/evidence_confidence/quality.py` | Evidence quality grade (Very High → Very Low) |
| `app/evidence_confidence/catalog_lookup.py` | Mechanism & molecular targets from KG |
| `app/evidence_confidence/constants.py` | Version strings and published weights |
| `app/schemas/explainability.py` | API/pipeline Pydantic models |

## Per-recommendation outputs

- `evidence_confidence_level` — High / Moderate / Low (structured)
- `evidence_confidence_numeric` — 0–1 score (feeds ranking after safety adjustment)
- `evidence_quality_grade` — Very High → Very Low (evidence hierarchy)
- `biological_rationale` + `explanation_chain` — biomarker → pathway → mechanism → intervention → evidence
- `supporting_biomarkers`, `supporting_pathways`, `molecular_targets`
- `evidence_timeline`, `contradictory_evidence`, `population_applicability`, `research_gaps`
- `why_recommended`, `why_not_higher`, `confidence_explanation`
- `confidence_factors[]` — full transparent factor breakdown
- `provenance[]` — PubMed / ClinicalTrials / knowledge-graph node trace
- `versioning` — KG, evidence, reasoning, explainability, report versions + timestamp

## Confidence algorithm (transparent)

Factors (see `scoring.py`):

| Factor | Weight |
|--------|--------|
| Study-type counts (RCT, meta-analysis, etc.) | per-type caps in `STUDY_TYPE_CONFIDENCE_CAP` |
| Publication recency | 0.08 |
| Consistency across studies | 0.10 |
| Biological plausibility (chain completeness) | 0.12 |
| Knowledge graph connectivity | 0.10 |
| Evidence quantity | 0.05 |
| Evidence quality (mean retriever score) | 0.10 |
| Safety data availability | 0.05 |
| Contradictory evidence penalty | up to −0.15 |

Thresholds: **High** ≥ 0.70, **Moderate** ≥ 0.45, else **Low**.

## Evidence quality hierarchy

Weights in `STUDY_TYPE_HIERARCHY_WEIGHT`:

Meta-analysis > Systematic review > RCT > Cohort > Case-control > Mechanistic > Preclinical > Animal > In vitro > Traditional use

## API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/explainability/evaluate` | Dry-run explainability |
| `GET` | `/api/v1/explainability/reports/{report_id}` | Explainability bundle for persisted report |

Explainability is also embedded on each recommendation in `GET /api/v1/reports/{id}` as `explainability`.

## Database

Migration `d4e5f6a7b8c9`:

- `recommendations.explainability` (JSON)
- `recommendation_reports.report_versioning` (JSON)

## Reproducibility

Reports are reproducible when:

- Same knowledge graph version (`KNOWLEDGE_GRAPH_VERSION`)
- Same evidence retrieval results
- Same explainability engine version (`EXPLAINABILITY_ENGINE_VERSION`)
- Same patient labs and pathway activations

Version metadata is stored on every report (`report_versioning`) and per-recommendation (`explainability.versioning`).

## Non-goals

- Does not generate recommendations
- Does not fabricate citations
- Does not replace clinician judgment
- Does not infer causality from observational data alone