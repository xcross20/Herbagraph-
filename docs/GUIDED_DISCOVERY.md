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

## SPEC: Phases 1–6 + LLM (additive)

**Problem:** A returning user cannot carry prior labs and case facts into Discovery, cannot ask why with real citations, and cannot attach an EMG/radiology *report* without pretending the lab parser is a new product — costing a disconnected investigation.

**Acceptance claims:**

1. Deterministic orchestrator still chooses the action when an LLM is present or absent.
2. LLM verbalization is discarded if it contains “you have” + a diagnosis, or if no API key is configured (fallback copy is used).
3. LLM-proposed findings are kept only when the name is on the intake allow-list.
4. `GET /patients/{id}/longitudinal-snapshot` returns a versioned snapshot built from existing labs + cases (not authored prose).
5. Asking “why” / “show evidence” attaches PubMed citations whose PMIDs came from NCBI, never invented strings.
6. `POST /cases/{id}/documents` classifies lab vs EMG vs radiology vs note; labs are not re-parsed here — they stay on the existing upload path.

**Non-goals:** Voice, Gold Label, Quest checkout, Next.js, pixel imaging diagnosis.

**Door class:** one-way for snapshot + literature JSON. Two-way for LLM prompt text.

## LLM rule

The LLM may explain the decomposition. It may not invent the numbers. Scores are deterministic from labs, profile, cited studies, and catalog tables. The conversation layer never decides clinical logic.

## DESIGN: Phases 1–6 + LLM (additive)

**Data model:** `discovery_cases.literature_json`; `discovery_longitudinal_snapshots(patient_id, version, is_current, payload)`. Snapshot payload is structured lists (concerns, symptoms, lab trends, medications, other diagnostics) — never authored prose.

**Seams:**

| Seam | Grade |
|---|---|
| Orchestrator / LLM | pass — LLM proposes facts and wording; allow-list + critic discard the rest |
| Documents / lab parser | fail-on-purpose for labs — 409, existing upload path only |
| Literature / PubMed | pass — NCBI E-utilities only; non-digit PMIDs dropped |
| Snapshot / new Case | pass — prior facts hydrate opening and later turns |
| Ask UI / workspace | pass — secondary portal; labs/reports stay primary |

**Decisions:**

| Decision | Door | Choice | Why |
|---|---|---|---|
| LLM writes findings | one-way | allow-listed names only | silent diagnoses must be unwritable |
| PMIDs | one-way | digits from NCBI | never invent literature |
| Lab documents in Discovery | one-way | refuse | do not fork the lab parser |
| Snapshot source | one-way | labs + cases | memory is derived, not authored |
| Next.js / voice / Gold Label | two-way | out | not required to ship 1–6 |

### ADR-4: LLM extracts and verbalizes; it does not steer — 2026-08-15 — accepted

**Context:** Master-tech wants language models in Discovery. CDS constraint: the model must not own clinical direction, scores, or diagnoses.

**Decision:** `app/discovery/ai.py` may propose allow-listed fact names and rewrite the predetermined action. `orchestrator.py` still selects the action. A critic discards “you have” + diagnosis copy. Missing or test API keys use the deterministic path.

**Alternatives:** LLM chat with tools — lost; the model would pick the next action. No LLM — lost; wording stays rigid and intake misses paraphrases.

**Consequences:** Turns stay correct with the LLM down. Production keys enable extract + verbalize. Test keys starting with `test-` stay deterministic.

**Revisit if:** allow-list growth needs a catalog, or verbalization must be streamed.

## RISK MAP: Phases 1–6 + LLM

1. Invented PMIDs in the Ask rail — P:M Cost:H Invisibility:H → retrieve only via `search_pubmed`; keep digit-only ids. Test: mock returns a non-digit id and it is dropped.
2. LLM writes a diagnosis into speech or findings — P:M Cost:H Invisibility:H → allow-list + critic + existing “you have” contract tests.
3. Document intake re-parses labs and forks the lab engine — P:M Cost:H Invisibility:M → classify + HTTP 409. Test: LabCorp text is refused.
4. Snapshot is authored prose the next case treats as truth — P:M Cost:H Invisibility:H → payload is lists from labs/cases only. Test: GET snapshot has structured keys, no diagnosis sentence.
5. Test `OPENAI_API_KEY=test-…` makes every turn call a live model — P:H Cost:M Invisibility:L → discovery LLM skipped for `test-` keys.
6. PubMed latency on every turn — P:M Cost:M Invisibility:L → retrieve only when the action is `retrieve_evidence`.

**Clean zones:** lab engine, four-score decomposition, existing upload path.

**Spike required:** none — PubMed client and `llm_client` already exist.

## SPEC: Safety & nuance engine (S0–S4)

**Problem:** A person with chronic, vague, or self-labeled symptoms cannot continue an investigation because a keyword match treats uncertainty as an emergency, costing either panic or a missed true acute pattern.

**Acceptance claims:**

1. Disposition is one of `S0` | `S1` | `S2` | `S3` | `S4`. There is no binary SAFE/URGENT.
2. “My gallbladder hurts.” is `S1` with clarifiers. It is not `S4`. The Case stores a patient interpretation, not a biliary diagnosis.
3. Case A (intermittent RUQ after eating, six months) is not `S4`. Case B (severe RUQ eight hours + repeated vomiting + fever) is `S4` and overrides Discovery. Case D (“I think I have sepsis because Google said so”) does not inherit the disease name and is not `S4`.
4. Historical jaundice plus current mild discomfort does not fire an acute emergency rule. Explicit “no fever, vomiting, or yellowing” is stored as absent, not omitted.
5. Sudden focal weakness (“this morning… I can't lift my right foot”) remains `S4` and still interrupts. Six-month burning feet remains Discovery (laterality), not an emergency.
6. Silent failure: safety copy never names an inferred disease (`sepsis`, `cholecystitis`, `you have`) and a hypothesis cannot independently escalate.

**Non-goals:** Hundreds of eval items, FDA clearance, LLM-authored disposition, replacing the intervention safety engine, Gold Label.

**Slices:** 1. Finding-driven S0–S4 + critic + safety net + NBA policy on the existing orchestrator.

**Door class:** one-way for `safety_status` values (`S0`–`S4`) and the safety payload on TurnState. Two-way for clarifier copy.

**Riskiest unknown:** whether S1 on every incomplete presentation will steal the first burning-feet laterality question.

## DESIGN: Safety & nuance

**Data model:** no new tables. `SafetyFinding` and `SafetyAssessment` are computed each turn from the current message plus prior fact map. The assessment is stored on the turn payload. `SafetyNet` is derived from the active domain.

**Seams:**

| Seam | Grade |
|---|---|
| Safety / hypotheses | pass — hypotheses never enter disposition |
| Safety / orchestrator | pass — assessment is an input to NBA, not a chat personality |
| Safety / lab-intervention safety engine | pass — different object |
| Safety copy / LLM | pass — composer verbalizes; critic blocks disease names |

**Decisions:**

| Decision | Door | Choice | Why |
|---|---|---|---|
| Five dispositions | one-way | S0–S4 | binary SAFE/URGENT cannot hold chronic uncertainty |
| Escalate on hypothesis | one-way | never | AHRQ: no premature closure / self-frightening |
| S1 vs burning-feet opening | two-way | S1 only for attention domains (abdominal, chest, inherited disease labels). Chronic sensory stays S2 | otherwise laterality is stolen |
| Persist SafetyNet table | two-way | derive + turn payload | recomputed from findings |

### ADR-5: Finding-driven five-level Discovery safety — 2026-08-15 — accepted

**Context:** Keyword `can't lift` / `gallbladder` / patient Google diagnoses were collapsing Discovery into a panic button.

**Decision:** Replace `routine`/`watch`/`urgent` with S0–S4. Consume FINDINGS (with acuity, chronology, trajectory, temporality, explicit negatives). Interpretations and hypotheses cannot escalate. S3/S4 pass a deterministic SafetyCritic. S4 overrides NBA; S1 asks 1–3 clarifiers; S0/S2 continue Discovery.

**Alternatives:** Keep binary urgent + more regex — lost; still no incomplete state. LLM triage — lost; model would own interruption.

**Consequences:** Public `safety_status` values change. Old `urgent`/`routine` payloads normalize on read. Verified: orchestrator already screens every turn. Guess: S1 will be the common early abdominal state.

**Revisit if:** counsel requires a different patient-facing claim, or S1 steals laterality on sensory cases.

## RISK MAP: Safety & nuance

1. Missed true emergency (sudden focal weakness / chest constellation) after the rewrite — P:M Cost:H Invisibility:H → keep those fixtures red-first; critic cannot downgrade a current multi-finding emergency.
2. False S4 from a disease name or historical red flag — P:H Cost:H Invisibility:H → only current/recent present findings; critic downgrades interpretation-only and historical-combo.
3. S1 steals burning-feet laterality — P:H Cost:M Invisibility:M → attention domains only; chronic sensory is S2. Test: existing fixture still asks `q_laterality`.
4. Safety copy names a diagnosis — P:M Cost:H Invisibility:H → composer + critic banned phrases; Case D test.

**Clean zones:** lab parser, PubMed, four-score decomposition, intervention safety engine.

**Spike required:** none — existing sudden-weakness and burning-feet fixtures are the spike.

## TEST REPORT: Safety & nuance

**Claims → tests:** S0–S4 (`test_disposition_is_five_levels_not_binary`); Case A/B/C/D; historical jaundice; explicit negatives; sudden focal vs chronic generalized weakness; crushing chest does not ask a scale; burning-feet laterality preserved; hypothesis text does not escalate.

**Risk map coverage:** missed emergency (foot + arm + chest); false S4 from Google/gallbladder/history; laterality theft; diagnosis copy.

**Red-first log:** follow-up stayed S1 until routine chronic pattern ranked above leftover jaundice unknown; “or yellowing” missed jaundice absence. Both re-seen green.

**NOT covered (declared):** hundreds of eval items; live KPI dashboard; FDA/counsel review.

## REVIEW: Safety & nuance

**Blocking:** none against the six claims.

**Should-fix:** expand the eval set beyond the named fixtures; measure false-alarm rate in production.

**Noted:** no new table — SafetyNet is derived each turn. Intervention safety engine untouched.

**Hostile trace log:** “I think I have sepsis” → interpretation stored, speech has no “sepsis”, not S4. Historical jaundice + mild discomfort ≠ S4. Burning feet still `q_laterality`.

**Verdict:** pass to SRE.

## OPS PLAN: Safety & nuance

**Signals:** S4 rate vs S1 rate on `/turns`; messages containing banned disease names; laterality stolen (S1 on burning-feet openings).

**Rollback:** revert the commit. No migration. Old `urgent`/`routine` payloads normalize on read. Strands nothing persisted except turn JSON that already existed.

**Launch:** web + worker. No reseed.

**Tripwires:** S4 on “gallbladder hurts” alone → critic/extract regression, revert. Sudden “can't lift” not S4 → emergency miss, revert immediately.

## SPEC: Discovery Guide Phase A

**Problem:** A person with an unstructured story (facial pressure after a shock, meal-related rib pain, fatigue and hair loss) cannot start a real investigation because Ask only understands a small regex catalog, costing a canned question or a dead end.

**Acceptance claims:**

1. When a live LLM is configured, the opening turn invokes Discovery Guide (not regex-only).
2. The facial-pressure fixture extracts reported symptoms, a timeline candidate, patient-reported MRI, and a patient interpretation — and does not store “trigeminal neuralgia” as a finding or say “you have.”
3. The Guide proposes 1–7 next-action candidates; deterministic safety can still force S4 and discard the Guide’s question.
4. If the LLM is absent or fails, the existing orchestrator still opens burning-feet with laterality.
5. Silent failure: a Guide-proposed disease name is dropped from findings; speech cannot contain “you have” + a diagnosis.

**Non-goals:** Voice, full tool roster, fine-tuning, Next.js `/discovery/{id}` rewrite, clinician review, lab ordering.

**Slices:** 1. This slice — two-pass Guide on opening and follow-up. 2. Context assembly + PubMed tool. 3. Live map proposals.

**Door class:** two-way for prompts and candidate scoring. One-way for “opening calls the Guide when a live key exists.”

## DESIGN: Discovery Guide Phase A

**Data model:** no new tables. `DiscoveryTurnPlan` is ephemeral JSON on the turn payload (`guide_plan`). Case findings still persist through the existing merge.

**Seams:** Guide / safety (pass — S4 wins). Guide / fact merge (pass — deny-list). Guide / orchestrator (pass — fallback). Prompts / code (pass — files composed at runtime).

### ADR-6: LLM-led consultation, deterministic validation — 2026-08-15 — accepted

**Context:** Peripheral LLM extract/verbalize could not handle a wide-range opening story.

**Decision:** `DiscoveryGuide.process_turn` is the conversation path. Pass A emits a structured plan. Safety, deny-list, and NBA scoring validate. Pass B writes speech for the selected action. No live key → current orchestrator.

**Alternatives:** Chat completion with no schema — lost; diagnoses leak. Keep regex-first Ask — lost; cannot run the facial fixture.

**Consequences:** Opening latency rises when the LLM is up. Tests stay deterministic via `test-` keys.

**Revisit if:** tool-calling replaces the two-pass JSON plan.

## RISK MAP: Discovery Guide Phase A

1. Opening writes a diagnosis from a long narrative — P:M Cost:H Invisibility:H → deny-list + speech critic + facial fixture.
2. S4 no longer interrupts because the Guide asked a question — P:M Cost:H Invisibility:H → safety still runs first; S4 returns only emergency action.
3. Live key down makes Ask empty — P:M Cost:H Invisibility:M → fallback orchestrator; burning-feet test.

**Clean zones:** lab parser, PubMed PMID filter, snapshot table.

**Spike required:** none — `llm_client` already exists.

## TEST REPORT: Phases 1–6 + LLM

**Claims → tests:**
1. Deterministic action with/without LLM → `test_orchestrator_ignores_off_list_llm_facts`, `test_orchestrator_discards_diagnosis_verbalization`, existing orchestrator fixture tests
2. Verbalization discarded on diagnosis / missing key → `test_critic_blocks_diagnosis_copy`, `test_verbalization_falls_back_when_critic_fails`, `test_missing_key_does_not_enable_discovery_llm`
3. Allow-listed facts only → `test_llm_facts_keep_allow_list_only`, `test_allow_list_does_not_include_diseases`
4. Versioned snapshot from labs + cases → `test_snapshot_payload_is_structured_not_a_diagnosis`, `test_longitudinal_snapshot_is_versioned_from_case`
5. Why/evidence attaches digit-only PMIDs → `test_retrieve_citations_keeps_digit_pmids_only`, `test_why_turn_attaches_digit_only_pubmed`
6. Documents classify; labs 409 → `test_classifies_lab_files_away_from_discovery`, `test_lab_document_is_rejected_with_409`, `test_emg_document_attaches_report_finding`

**Risk map coverage:** invented PMIDs; LLM diagnosis; lab reparse; snapshot prose; test-key LLM; urgent vs evidence.

**Red-first log:** three tests failed first (test-key settings cache, “can't I lift” not matching safety, unauth client shared headers). Re-seen green after fixture/test fixes. Remaining tests written against the spec and passed on this run.

**NOT covered (declared):** live NCBI or live MiniMax; binary PDF OCR; voice; Gold Label; user-edit of memory.

## REVIEW: Phases 1–6 + LLM

**Blocking:** none found against the six acceptance claims.

**Should-fix:** snapshot writes a new version on every turn (table growth). GET snapshot mutates when missing. Ask attach is paste-text only.

**Noted:** allow-list is narrow; `ct ` classifier is space-sensitive; two sync LLM calls can block the event loop in production.

**Hostile trace log:** LabCorp + reference-range text → 409. Fake `PMID:not-real` dropped. “You have small-fiber neuropathy” discarded. Urgent “can't lift” + this morning still beats “why”.

**Verdict:** pass to SRE.

## OPS PLAN: Phases 1–6 + LLM

**Signals:** `/health`; 409 rate on `POST /cases/{id}/documents`; empty `literature` after retrieve_evidence; snapshot version incrementing on `GET /patients/{id}/longitudinal-snapshot`; Discovery turn 5xx.

**Rollback:** revert the git deploy; migration `s9t0u1v2w3x4` is expand-only (`literature_json` nullable + new snapshot table). Rollback strands snapshot rows and literature JSON until downgrade. Lab upload path is untouched.

**Launch:** push `main`; Railway web `Herbagraph-` + Worker Service; confirm `alembic upgrade head` in start script; no reseed required.

**Tripwires:** document 409s with EMG filenames (classifier too eager on labs) → inspect `classify_document`; literature rows with non-digit pmid → fail the retrieve filter; “you have” in system turns → critic regression, revert verbalization.
