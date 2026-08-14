# Guided Discovery — architecture reset without a rewrite

**Status:** accepted for slice 1 (confidence decomposition). Later slices add Case / Hypothesis / Investigation objects.  
**Date:** 2026-08-14

## SPEC: Why a 78% score is not useful

**Problem:** Clinicians and operators cannot tell whether a recommendation sits at ~78% because the science is weak, the patient does not match, the workup is incomplete, or the graph is thin — so they cannot decide whether to act, test further, or stop, costing either missed action or indiscriminate panels.

**Acceptance claims:**

1. Every recommendation explainability payload includes four independent scores in 0–1: `evidence_confidence`, `patient_match`, `data_sufficiency`, `decision_confidence`.
2. The four scores can diverge on the same intervention (a test fixture with strong RCTs and empty patient context has evidence ≫ data sufficiency).
3. When confirmatory markers for the intervention/pathway are absent (e.g. B12 without MMA/homocysteine), `data_sufficiency` lists those markers and `gap_analysis` names them with an expected gain.
4. `decision_band` is one of `action` | `investigate` | `stop`. The engine never recommends more tests solely to push decision confidence over 0.90.
5. An audit script classifies the primary bottleneck across catalog-only scenario recommendations (context / biomarkers / evidence / contradiction / graph).
6. Silent failure: the UI must not display a single percentage as if it were “how true the conclusion is” when data sufficiency is the limiter — the report shows all four scores.

**Non-goals (this slice):**

- Case / Finding / Hypothesis / Investigation persistence
- Chat-driven Guided Discovery loop
- Next.js rewrite
- Gold Label commerce
- Imaging/EMG/biopsy parsers
- Graph neural nets
- Forcing any score to 90%
- Replacing the existing lab pipeline

**Slices:**

1. **This slice** — decompose existing lab-engine recommendations; gap analysis; audit; report UI.
2. Persistent Case + Finding + Hypothesis objects wrapping the lab engine.
3. Investigation coverage by clinical branch + grouped test utility.
4. Discovery fifth score (investigation relevance vs diagnostic certainty).

**Door class:** one-way for the public explainability JSON shape (report consumers and UI will depend on the four keys). Two-way for weights and marker tables.

**Riskiest unknown:** whether today’s ~75–80% ceiling is mostly missing context, evidence-quality weighting, or missing markers. The audit script exists to answer that before we grow the graph blindly.

---

## DESIGN

**Data model (this slice):** no new tables. Decomposition is computed at explainability time and stored on the existing `recommendations.explainability` JSON.

**Later (not built):** Case, Finding, Hypothesis, Investigation, Evidence, Intervention, Outcome — seven core objects. Labs remain one evidence modality.

**Seams:**

| Seam | Grade |
|---|---|
| `decomposition.py` / existing `scoring.py` | pass — evidence numeric reused, not rewritten |
| decomposition / health_profile + labs | pass — pure functions, fixture-tested |
| explainability JSON / report UI | pass — optional field, old reports still render |
| Case persistence | deferred — failing this seam on purpose until slice 2 |

**Decisions:**

| Decision | Door | Choice | Why |
|---|---|---|---|
| Four scores vs one | one-way | four + decision band | a single 78% cannot say *why* |
| Next.js rewrite | two-way | keep FastAPI + static frontend | rewrite is not required to ship explainability |
| Microservices | two-way | modular monolith | no demonstrated split need |
| LLM writes scores | one-way | never | FDA-safe CDS: clinician can review the basis |
| Test until 90% | one-way | three bands (action / investigate / stop) | AHRQ threshold model; no incentive for junk panels |

### ADR-1: Four first-class scores on recommendations — 2026-08-14 — accepted

**Context:** The evidence confidence engine already emits `evidence_confidence_numeric` plus factor lists. Operators still cannot separate “the papers are moderate,” “this patient is a poor match,” and “we do not have enough data.”

**Decision:** Add `confidence_decomposition` on each recommendation explainability object with independent `evidence_confidence`, `patient_match`, `data_sufficiency`, and a derived `decision_confidence`. Keep the legacy numeric for ranking compatibility.

**Alternatives:**

- Replace the old score in place — lost; ranking and stored reports would change meaning silently.
- Only add prose `why_not_higher` — lost; prose is not auditable or aggregable.

**Consequences:** New reports carry more JSON. Old reports lack the block (UI degrades). Weights are versioned (`decomposition_v1`). Verified: existing `explainability` column is JSON. Guess: clinicians will use sufficiency vs decision as the primary pair.

**Revisit if:** Case objects land and scores must attach to hypotheses, not only interventions.

---

## Decision bands (not a 90% hunt)

- **action** — decision ≥ 0.70 and sufficiency ≥ 0.35: enough to reasonably consider the intervention class (not a prescription).
- **stop** — sufficiency ≥ 0.80 and decision < 0.55: plenty of data; evidence is genuinely ambiguous. Do not add tests to chase a higher number.
- **investigate** — otherwise: named gaps could change the decision.

Test utility (later slice): information gain × actionability × safety × coverage ÷ (cost + burden + risk + redundancy). This slice only *names* gaps; it does not order 20 tests.

---

## LLM rule

The LLM may explain the decomposition. It may not invent the numbers. Scores are deterministic from labs, profile, cited studies, and catalog tables.
