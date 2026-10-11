# Five-Service Frontend and Backend Implementation Map

**Issue:** #65  
**Architecture:** Extend the current workspace and FastAPI modular monolith  
**Primary rule:** One Case, one Case version, one Personal Evidence Object model

## 1. Repository impact map

| Existing area | Decision | Why |
|---|---|---|
| `app/main.py` | Keep | Current FastAPI/static deployment remains. |
| `app/api/v1/router.py` | Extend | Add one personal-evidence router. |
| `app/models/discovery.py` | Keep Case/Discovery entities | They remain canonical investigation state. Avoid overloading with product-specific columns. |
| `app/discovery/service.py` | Extend through command/projection seam | Case persistence and coherent snapshots remain authoritative. |
| `app/discovery/orchestrator.py` | Read personal-evidence summaries; do not own experiment truth | Ask can verbalize and route, but cannot become the experiment database. |
| `app/discovery/composition.py` | Extend behind identity service | Reuse form/parent/elemental concepts; move production identity acceptance into governed personal-evidence domain logic. |
| `app/discovery/data/composition_graph_v1.json` | Keep as bounded seed/certification data | It is not a comprehensive commercial product catalog. |
| `app/pipeline/` | Reuse evidence/lab/safety components | Labs remain labs; evidence and safety contracts are reused where inputs match. |
| Existing intervention engine | Reuse eligible claim/safety primitives | Do not call biomarker recommendation logic from symptom-only inputs. |
| `frontend/js/workspace-app.js` | Extend shell/navigation and module mounting | Primary application remains the workspace. |
| `frontend/js/ask-app.js` | Extend commands and summaries | Ask invokes the same canonical modules and projections; it does not duplicate them. |
| Existing frontend CSS/HTML | Extend design tokens/components | No framework rewrite in Phase I/MVP slices. |
| Celery/Redis | Extend routing | Use existing operations with bounded personal-evidence queues. |
| PostgreSQL/Alembic | Extend additively | One transactional truth store. |
| Existing consent work | Extend by purpose | Product and research grants remain separate. |
| GitHub autonomous loop | Extend with qualified roles | Preserve exact-SHA review and Founder gates. |

## 2. Workspace information architecture

Add a `My Evidence` section to the existing personal workspace navigation. Do not put five equal top-level products in the sidebar during the first slice.

Recommended hierarchy:

```text
Dashboard
Ask
My Evidence
  Today
  Regimen
  Signals
  Experiments
  Passport
Labs
Case / Investigation
Settings / Consent
```

For clinic roles, the same modules appear inside the selected patient context with read/review permissions determined by role and sharing consent.

### Route strategy

The current workspace uses static HTML and hash-based navigation. Add routes incrementally:

- `/me.html#evidence-today`
- `/me.html#regimen`
- `/me.html#signals`
- `/me.html#experiments`
- `/me.html#passport`

Ask remains `/ask.html` and deep-links to the canonical workspace state.

Do not create a second SPA shell. Add a small module registry in `workspace-app.js` initially, then extract files when the first module exceeds a maintainable boundary:

```text
frontend/js/
  personal-evidence/
    api.js
    state.js
    components.js
    today.js
    regimen.js
    signals.js
    experiments.js
    passport.js
```

The extraction can occur in Slice 1 without changing deployment or framework.

## 3. Shared frontend contract

### Atomic Case view

Every module response includes:

- `case_id`
- `case_version`
- `snapshot_id`
- `generated_at`
- `data_completeness`
- `unresolved_count`
- `permissions`
- `feature_flags`

Chat, workspace modules, literature, action plans, and Passport previews must use the same Case version for a rendered view. If a response is stale, mark the entire affected view stale and refresh coherently. Never mix a current chat answer with an old Signals or Regimen panel.

### Shared status vocabulary

Use:

- verified
- user confirmed
- reported
- candidate
- unresolved
- partial
- stale
- superseded
- ineligible
- insufficient data
- inconclusive

Do not use “normal,” “safe,” “works,” “caused,” or “recommended” without the governed scientific meaning.

### Required states for every module

- initial/loading
- empty
- success
- partial
- uncertain/unresolved
- stale snapshot
- permission denied
- safety escalation
- provider/API unavailable
- validation error
- interrupted work preserved
- correction/supersession
- feature disabled

### Accessibility

- WCAG 2.2 AA target
- semantic headings and landmarks
- keyboard completion
- 44-by-44 minimum touch targets
- no color-only meaning
- screen-reader announcements for uncertainty, stale state, safety, and saved corrections
- 200 percent zoom/reflow
- focus restoration after dialogs and atomic refresh
- reduced-motion support
- plain-language labels over internal ontology terms

## 4. Service 1: Regimen

### User job

“I need a trustworthy account of what I take, in what form and amount, without reconstructing it from memory.”

### Frontend

Primary screens:

1. Regimen overview
2. Add product: photo, barcode candidate, search, or manual entry
3. Extraction review
4. Identity confirmation
5. Daily schedule/timeline
6. Ingredient overlap
7. Regimen version history
8. Correction flow

Regimen card displays:

- product name and manufacturer
- decision-relevant form
- label versus active/elemental amount
- serving basis
- route and timing
- purpose in user language
- verification status
- unresolved fields
- start/stop history

No product becomes active through OCR alone.

### Backend

New package responsibilities:

- `identity.py`: product fingerprint, field confidence, confirmation rules, parent/form relationships.
- `regimen.py`: regimen version publication, item lifecycle, overlap calculations.
- `commands.py`: confirm identity, add/stop/correct item.
- Identity workers: OCR and external catalog candidate generation.

Tables:

- `pe_product_captures`
- `pe_product_identities`
- `pe_identity_confirmations`
- `pe_regimen_versions`
- `pe_regimen_items`

First API:

- create capture
- poll capture
- confirm identity
- get current regimen
- create/stop/correct regimen item
- get version history

### Reused HerbaGraph components

- encrypted upload/object storage
- user/patient authorization
- composition graph concepts and form examples
- provenance patterns
- append-only correction rules
- safety and interaction primitives
- Case version and snapshot response

### Slice-1 acceptance

- OCR uncertainty remains field-level and visible.
- Exact form and active amount can remain unresolved.
- User confirmation is required before active use.
- Replayed finalize/confirm requests are idempotent.
- Regimen changes create history rather than overwrite it.
- Compound and elemental amount are never conflated.
- Seed ontology examples never enter a Case without active identity relevance.

## 5. Service 2: Signals

### User job

“Show me patterns worth investigating without pretending you have proven the cause.”

### Frontend

Primary screens:

1. Signals inbox
2. Signal detail with overlaid timeline
3. Evidence for / evidence against
4. Missing data and confounders
5. “Collect more data” or “Test this safely” eligibility
6. Reject/not relevant
7. Why this appeared

A signal card displays:

- exposure and outcome
- temporal pattern
- supporting event count
- contradictory event count
- completeness
- important confounders
- method/version
- status and allowed interpretation

Avoid disease-style rankings or red/green causality colors.

### Backend

Responsibilities:

- `observations.py`: typed outcomes/context and time semantics.
- `signals.py`: transparent candidate generation, windows, lags, contradictions.
- `eligibility.py`: whether enough data exists to propose further observation or an experiment.

Tables:

- `pe_exposure_events`
- `pe_observation_events`
- `pe_context_events`
- `pe_candidate_signals`
- `pe_signal_event_links`

Workers may compute candidates. A governor verifies temporal order, identity, missingness, and confounder disclosure before display.

### Reused components

- Discovery observation/finding concepts where semantically compatible
- Case timeline and append-only corrections
- investigation-family relation for context
- evidence cards and explanation drawer
- shared snapshot ID
- non-diagnostic language governor

### Slice-2 acceptance

- Missing check-in is never encoded as zero.
- Symptom improvement beginning before exposure cannot support the signal.
- Multiple simultaneous changes are visible.
- Corrections invalidate or supersede dependent candidates.
- Candidate generation cannot create a recommendation.
- Repeated jobs cannot create duplicate signals.

## 6. Service 3: Experiments

### User job

“Help me test one safe change in a structured way I can realistically complete.”

### Frontend

Primary screens:

1. Experiment eligibility
2. Question and expected learning
3. Protocol preview
4. Safety and exclusion review
5. Consent/purpose
6. Active phase / Today task
7. Check-in
8. Adherence and deviations
9. Pause/stop
10. Completion readiness

The screen must explain:

- why this design was chosen
- what remains stable
- what is measured
- how long and why
- burden
- what would invalidate interpretation
- stop/escalation conditions
- what the result cannot prove

Prompts must be outcome-neutral. Do not ask “Did the supplement help today?”

### Backend

Responsibilities:

- `eligibility.py`: deterministic safety and interpretability rules.
- `experiments.py`: template, phases, transitions, deviations.
- `events.py`: protocol event lifecycle.
- existing safety layer: interaction/contraindication inputs when applicable.

Tables:

- `pe_experiment_protocols`
- `pe_experiment_phases`
- `pe_protocol_events`
- `pe_safety_events`

Initial designs:

- stable baseline then one introduction
- observation-only protocol when intervention is ineligible
- withdrawal/randomized/rechallenge only in later approved templates

### Reused components

- supportive-action safety priority
- Case findings and active constraints
- consent and audit patterns
- monitoring events
- response-mode recognition for “what can I do now?”
- notification infrastructure if present; otherwise defer

### Slice-3 acceptance

- One primary question and one primary outcome.
- Exact intervention identity required.
- Unsafe/essential intervention changes fail closed.
- Serious prior reaction blocks unsupervised rechallenge.
- Baseline, adherence, missingness, confounders, and stop rules are preregistered.
- LLM cannot activate a protocol.
- Product and research purposes remain separate.

## 7. Service 4: Attribution

### User job

“Tell me what the data suggests, how uncertain it is, and what else could explain it.”

### Frontend

Primary screens:

1. Data-readiness summary
2. Timeline and phases
3. Effect estimate
4. Adherence and missingness
5. Confounders and alternative explanations
6. Sensitivity results
7. External evidence
8. Allowed conclusion
9. What would strengthen or weaken it
10. Accept for Passport / request review

Do not lead with one confidence percentage. Show confidence dimensions:

- identity
- data completeness
- protocol fidelity
- temporal association
- consistency
- confounding risk
- external evidence
- safety certainty
- attribution certainty

### Backend

Responsibilities:

- `attribution.py`: deterministic, versioned methods.
- `projections.py`: interpretable result contract.
- evidence retriever: exact form/population/endpoint applicability.
- Independent Judge fixtures: wrong form, missingness, carryover, natural cycling, simultaneous changes.

Tables:

- `pe_attribution_analyses`
- `pe_analysis_inputs`
- `pe_analysis_sensitivity_results`
- `pe_analysis_reviews`

Initial analysis may use transparent baseline-versus-intervention estimates and plots. More complex Bayesian or randomized-period methods require dedicated validation; sophistication is not itself validity.

### Reused components

- evidence grade and claim cards
- scientific-output gate
- pathway explanations as context, never measured truth
- provenance
- monitoring outcomes and causal-claim taxonomy
- LLM rendering restrictions

### Slice-4 acceptance

- Analysis version and data cutoff are immutable.
- Missingness and adherence affect eligibility/interpretation.
- Invalid or confounded analysis renders `inconclusive` or `invalid`.
- External literature must match identity, route, population, comparator, endpoint, and duration.
- Improvements do not become proof of cause.
- Reanalysis creates a new version.

## 8. Service 5: Passport

### User job

“Remember what I tried and give me something credible that I can use later or show a clinician.”

### Frontend

Primary screens:

1. Passport overview
2. Personal Evidence cards
3. Regimen history
4. Helpful/possible/no-difference/adverse/inconclusive groups
5. Unresolved and superseded items
6. Clinician preview
7. Share/export controls
8. Version history
9. Revoke sharing

A Personal Evidence card shows:

- exact intervention
- exact question
- observation period
- protocol fidelity
- result class
- confidence dimensions
- important alternatives
- supporting evidence
- limitations
- source Case version
- review status

### Backend

Responsibilities:

- `passport.py`: accepted evidence-object projection and publication.
- `projections.py`: consumer, clinician, JSON formats.
- sharing/consent: purpose, recipient, version, expiration, revocation.
- audit: publication, export, share, revoke, correction.

Tables:

- `pe_personal_evidence_objects`
- `pe_passport_versions`
- `pe_passport_entries`
- `pe_share_grants`

### Reused components

- existing report generation patterns
- clinician/personal role separation
- Case and patient summaries
- evidence provenance
- disclaimers and limitations
- encrypted document storage where export files are persisted

### Slice-5 acceptance

- Passport is a projection, not a new source of truth.
- Each entry traces to exact Case and analysis versions.
- Unresolved and contradictory information is not hidden.
- Old versions remain immutable.
- Sharing is version-specific and auditable.
- Revocation blocks future access without rewriting historical audit.
- Commerce cannot change inclusion or ordering.

## 9. Today experience

`Today` is the cross-service home, not a sixth service.

It may show:

- one pending identity confirmation
- scheduled experiment action
- one neutral check-in
- safety status
- missed/late observation
- recent accepted signal
- Passport update ready

Selection is deterministic by safety, protocol deadline, information value, and burden. It is not optimized for generic engagement.

## 10. Ask integration

Ask may interpret:

- “Add this supplement.”
- “I took it this morning.”
- “What changed this week?”
- “Could this be a trigger?”
- “Help me test this.”
- “What did I learn?”
- “Show my Passport.”

Ask creates the same typed commands used by the workspace. It never maintains hidden chat-only regimen, exposure, protocol, analysis, or Passport state.

Before a material mutation, Ask confirms any missing identity, time, dose, consent, or safety field that makes the command invalid. After mutation, chat and workspace render the same snapshot.

## 11. Frontend state management

For the existing static application:

- add one shared `personal-evidence/state.js` module
- cache only read projections keyed by Case version
- discard module caches when a newer Case version is accepted
- serialize mutation requests per Case
- send explicit idempotency keys and expected Case version
- preserve unsent form state locally without treating it as saved truth
- render provider failure and partial state honestly

Do not use local storage as medical truth. It may hold non-sensitive UI preferences and recoverable unsent drafts under approved privacy rules.

## 12. Backend package seams

| Package | Owns | Must not own |
|---|---|---|
| identity | product candidate, fingerprint, confirmation | evidence conclusions or commerce rank |
| regimen | planned/reported schedule and versions | actual exposure |
| observations | actual exposure/outcome/context events | causal interpretation |
| signals | candidate relationships | protocol activation |
| eligibility | safety/interpretability gate | user-facing free generation |
| experiments | protocol and phase state | analysis truth |
| attribution | versioned analysis | product identity confirmation |
| passport | accepted projection and sharing | canonical Case truth |
| projections | coherent versioned reads | mutations |
| events | transactional domain events | business-policy decisions |
| telemetry | non-PHI metrics | health payloads |

## 13. First implementation target

Do not start with Signals or AI analysis. Start with Regimen Truth:

`label/manual input -> candidate -> user confirmation -> regimen version -> workspace projection -> correction`

This slice creates immediate commercial value, supports NIH identity-feasibility endpoints, and is a prerequisite for every later module.

The first implementation issue must not add personal experiments, causal analysis, public research claims, or production activation.

The trap: a fast Signals experience built before exact identity and typed time would generate impressive patterns about the wrong intervention.
