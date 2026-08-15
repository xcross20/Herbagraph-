# Guided Discovery — architecture reset without a rewrite

HerbaGraph is an event-driven, case-centered clinical investigation platform. The persistent Case—not the chat transcript—is the source of truth. AI generates typed candidate reasoning; deterministic services validate and reconcile that reasoning against structured findings, provenance, safety rules and the knowledge graph. Laboratory analysis is one evidence modality within the broader investigation system. Interventions are separate from products, and commerce can only occur downstream of clinical relevance and safety determination.

The seven core objects are Case, Finding, Hypothesis, Investigation, Evidence, Intervention, and Outcome. Turn is the eighth: a traceable state transition, not a chatbot utterance.

**Status:** slices 1–3 accepted. Slice 4 — turn orchestrator — in progress.  
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

## Slice 2 — Case as source of truth

**Problem:** A person starts with a concern (“feet burn at night”) but HerbaGraph only persists lab reports, so hypotheses and investigation coverage vanish between requests.

**Acceptance:**

1. `POST /api/v1/cases` with a presenting concern returns a persisted Case.
2. Rebuild with B12 low + MCV high produces a B12/one-carbon hypothesis whose relevance > certainty, with MMA listed as missing.
3. Investigations are grouped core / directed / conditional.
4. Branch coverage is reported as “how thoroughly this branch was assessed,” not disease probability.
5. The engine never writes a diagnosis; empty input yields no hypotheses.

### ADR-2: Persist Case / Finding / Hypothesis — 2026-08-14 — accepted

**Context:** Slice 1 decomposes intervention scores. Discovery still had no object that survives a request.

**Decision:** Three tables (`discovery_cases`, `discovery_findings`, `discovery_hypotheses`). Rebuild is a pure function (`app/discovery/engine.py`). The LLM does not write findings or close hypotheses.

**Alternatives:** JSON-only column on analysis_session — lost; buries the Case inside a lab session. Separate microservice — lost; no scale need.

**Consequences:** Schema is a one-way door. Existing lab engine unchanged. GET returns the last snapshot, not a live LLM story.

**Revisit if:** Findings need their own query API or outcomes must attach.

### Workspace modes (consumer vs clinician)

Two portals, one API:

- `/me.html` — personal portal (`individual`)
- `/clinic.html` — clinician portal (`clinician` / admin)
- `/app.html` — router that sends the signed-in user to the correct portal

Discovery also emits `next_questions` (question engine) and `what_changed` (rebuild reconciliation).

Conversation is turn-based: the system asks **one** current question, waits, then asks the next. Typing `yes` / `no` / `not sure` answers that question. The Case stays the source of truth; chat is only the interface.

## Slice 3 — Answerable Discovery + outcomes + chat as interface

**Problem:** Clinicians and individuals land in the same workspace shape, and Discovery questions cannot be recorded, so coverage never updates from conversation and the Case is not actually the source of truth.

**Acceptance claims:**

1. Clinicians land on `/clinic.html` (panel, many patients). Individuals land on `/me.html` (one Self profile). Visiting the wrong portal redirects.
2. `POST /api/v1/cases/{id}/answers` with yes/no/unknown persists an Outcome. Yes records an assessment finding so the named marker is no longer missing and coverage can rise.
3. Test utility is the documented formula (information gain × actionability × safety × coverage gain) ÷ (cost + burden + risk + redundancy). MMA ranks above skin biopsy.
4. Chat is only an interface: a turn opens or updates the Case. The engine never writes a diagnosis into a turn.
5. Silent failure: rebuild after an answer must keep previously ingested labs (not drop B12/MCV just because they were not a LabReport row).

**Non-goals:** Gold Label, imaging parsers, Next.js, LLM-authored scores, 90% confidence hunt, admin case console.

**Door class:** one-way for `discovery_outcomes` / `discovery_turns` schema. Two-way for question copy and portal chrome.

## SPEC: Atlas Discovery workspace (master-tech Phase 1)

**Problem:** A person investigating burning feet cannot see what HerbaGraph knows, what it is investigating, and what would increase confidence in one workspace, so Discovery still looks like a chatbot and they cannot tell whether they should answer, upload, or stop.

**Acceptance claims:**

1. Discovery desktop shows three panels: Health memory, Conversation, Investigation.
2. Memory items carry a provenance badge (reported / unverified / inferred), never silently confirmed.
3. Investigation panel lists hypothesis families with relevance and coverage, plus “what would increase confidence,” and never a disease probability.
4. `GET /api/v1/cases/{id}/investigation-map` returns a versioned map; a material turn increments the version.
5. Silent failure: the conversation still cannot say “you have small-fiber neuropathy.”
6. First session requires acknowledging the educational/not-a-diagnosis disclaimer.

**Non-goals:** Next.js rewrite, voice, Gold Label, Quest/Labcorp checkout, Kafka, imaging parsers.

**Slices:** 1. Atlas shell + map API + confidence list on the existing FastAPI/static stack.

**Door class:** one-way for investigation-map JSON. Two-way for CSS/layout.

**Riskiest unknown:** whether the existing Case payload already contains enough to fill both side panels without a Patient Snapshot table.

## DESIGN: Atlas + versioned map

**Data model:** `discovery_map_versions(case_id, version, payload_json)`. Map is derived from Case findings + hypotheses + unknowns. Patient Snapshot table deferred.

**Seams:** map builder / orchestrator — pass (pure). map API / CaseRead — pass. Atlas CSS / existing workspace-app — fail-on-purpose until this slice (layout was single-column).

**Decisions:** Keep static frontend (two-way) instead of Next.js — rewrite is not required to ship Atlas. Version maps on payload hash change (one-way JSON).

## RISK MAP: Atlas slice

1. Rebuild wipes map versions — P:L Cost:H Invisibility:H → append-only versions, never delete. Test: version increments, old version remains.
2. UI implies diagnosis via panel labels — P:M Cost:H Invisibility:H → copy review + contract test forbids “you have” / disease %.
3. Mobile three-column crush — P:H Cost:M Invisibility:L → tabs under 900px.

**Clean zones:** orchestrator action selection, lab engine.

**Spike required:** none — CaseRead already has findings, hypotheses, unknowns, problem_representation.

## Slice 4 — Turn orchestrator

**Problem:** Discovery still behaves like a question list. A real investigation turn must update the Case first, then choose a next action, then speak — otherwise the chat decides clinical direction.

**Acceptance claims:**

1. The fixture “For six months, my feet have burned at night…” creates a Case, extracts burning / feet / night / ~6 months / claimed-normal labs, and does **not** say “you have small-fiber neuropathy.”
2. The first conversational action is a laterality question with a single-select, not a dumped differential.
3. Sudden onset plus new weakness selects `show_safety_message` and pauses discovery.
4. Every turn returns a TurnState: stage, safety, intents, new findings, selected action, why we are speaking.
5. “I don't know” stores unknown and does not re-ask that gap.
6. Contradictory laterality selects `clarify`.
7. A reported-normal EMG selects `request_record` with a file-upload interaction.
8. Silent failure: the conversation layer cannot invent an action the reasoner did not select.

**Non-goals:** Gold Label commerce, imaging parsers, LLM-authored clinical logic, Next.js.

**Door class:** one-way for Turn payload / action JSON. Two-way for question copy.

### ADR-3: Turn orchestrator is the conversation engine — 2026-08-14 — accepted

**Context:** One-question-per-turn UI still let the chat surface choose direction. The product mandate is a hidden state machine.

**Decision:** `app/discovery/orchestrator.py` is the only path for user text. Order is fixed: persist → intent → safety → extract → mutate Case → rebuild hypotheses → critic → next-best action → compose response. The composer verbalizes the action; it does not pick it.

**Alternatives:** LLM chat with case context — lost; the model would own clinical direction. Keep yes/no-only questions — lost; cannot run the burning-feet fixture.

**Consequences:** DiscoveryTurn stores action, stage, and payload. Opening no longer lists hypothesis families in prose.

## LLM rule

The LLM may explain the decomposition. It may not invent the numbers. Scores are deterministic from labs, profile, cited studies, and catalog tables. The conversation layer never decides clinical logic.
