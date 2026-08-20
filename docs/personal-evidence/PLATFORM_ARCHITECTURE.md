# HerbaGraph Personal Evidence Platform Architecture

**Status:** Founder-authorized architecture proposal  
**Issue:** #65  
**Target:** `integration/agent`  
**Scope:** Five services over one longitudinal Case  
**Implementation posture:** Modular monolith; no frontend rewrite; UAT first

## 1. Outcome

HerbaGraph will add one coherent personal-evidence loop:

`REGIMEN -> SIGNALS -> EXPERIMENT -> ATTRIBUTION -> PASSPORT -> UPDATED CASE`

The five customer-facing services are:

1. **Regimen** — identify exactly what a person uses, how much, when, and why.
2. **Signals** — surface candidate exposure-response relationships without asserting cause.
3. **Experiments** — create bounded, safety-governed personal protocols when eligible.
4. **Attribution** — estimate an individualized response with explicit uncertainty and alternatives.
5. **Passport** — preserve a versioned, shareable account of what was tried and learned.

They are modules, not applications. Every module reads and writes the same canonical Case through governed commands. None may maintain a private competing health record.

## 2. Current architecture that remains

The first implementation must extend the repository as it exists on `integration/agent`.

### Runtime

Keep:

- `app/main.py`: FastAPI application and static frontend mount.
- `app/api/v1/router.py`: versioned API composition.
- SQLAlchemy 2.x models, async sessions, Alembic, PostgreSQL production storage, and SQLite-compatible tests where currently supported.
- Celery and Redis for asynchronous work.
- Existing authentication, users, patients, roles, owner scoping, encrypted upload storage, correlation IDs, and environment metadata.
- Railway UAT and the current promotion gates.

Do not introduce microservices, a second database, Kafka, a graph database, or Next.js merely to create conceptual cleanliness. Future extraction is allowed only after an independently deployable scaling, security, or ownership boundary is demonstrated.

### Canonical Case and Guided Discovery

Keep and extend:

- `app/models/discovery.py::DiscoveryCase` as the aggregate root for a supported personal investigation.
- `DiscoveryFinding` for active and superseded user-reported or imported facts.
- `DiscoveryTurn` for conversation history and idempotent turn persistence.
- `DiscoveryMapVersion` for append-only map projections.
- `DiscoveryInvestigationBranch`, evidence gaps, workup items, and evidence edges for coverage-aware investigation.
- `app/discovery/service.py` as the persistence boundary between the reasoning engine and database.
- `app/discovery/orchestrator.py`, governors, response modes, and canonical action-plan rendering.
- The shared `case_version` / `snapshot_id` concept introduced for coherent chat, panel, explanation, literature, and action-plan projections.

The Case does not become a conversation object or an experiment object. Experiments and evidence are children of the Case, and all user-facing projections declare the Case version used.

### Existing science and evidence systems

Keep and extend:

- `app/pipeline/` laboratory parser, normalizer, pathway mapping, evidence retrieval, LLM reasoning, safety, and report generation.
- The existing biomarker and lab entities. Personal-experiment observations do not masquerade as laboratory results.
- `app/discovery/composition.py` and `app/discovery/data/composition_graph_v1.json` as an initial identity and composition layer.
- Seed/example-content exclusion rules.
- Evidence claim cards, applicability limitations, literature provenance, and citation gates.
- Existing intervention and supportive-action machinery where eligibility semantics match. Symptom-only input must not invoke measured-biomarker logic.

### Current frontend

Keep:

- `frontend/js/workspace-app.js` as the primary personal/clinic workspace controller.
- `frontend/js/ask-app.js` as the secondary conversational surface over the same Case.
- Existing authentication utilities, app shell, personal/clinic role behavior, responsive navigation, upload workflow, and UI environment labeling.
- Existing shared CSS and static HTML build/deployment.

New services enter the workspace incrementally. A framework migration is a separate future decision requiring measured maintenance or product benefit.

## 3. New domain boundary

Add a bounded package family:

```text
app/
  personal_evidence/
    __init__.py
    commands.py
    identity.py
    regimen.py
    observations.py
    signals.py
    eligibility.py
    experiments.py
    attribution.py
    passport.py
    projections.py
    events.py
    telemetry.py
  models/
    personal_evidence.py
  schemas/
    personal_evidence.py
  api/v1/
    personal_evidence.py
  tasks/
    personal_evidence.py
```

This is a package boundary inside the existing deployable application.

### Dependency direction

- API receives a typed command.
- Command handler validates owner, Case version, idempotency, consent purpose, and domain invariants.
- Domain logic produces accepted events and projection changes.
- SQLAlchemy persistence commits state and outbox messages atomically.
- Workers perform low-authority candidate generation or analysis.
- Deterministic governors validate worker results before durable acceptance.
- Frontend receives one coherent `CaseViewRead` projection.

The frontend never writes directly to tables. Workers never bypass command handlers to create clinically meaningful state.

## 4. Canonical data model

### Case relationship

A `DiscoveryCase` has zero or more regimen versions, products, exposure events, observations, candidate signals, experiment protocols, analyses, and Passport versions.

The Case remains the owner. Patient-level longitudinal summaries may project across Cases only through the existing patient memory contract.

### ProductCapture

Represents a label image, manual entry, barcode result, or imported product record.

Fields:

- `id`, `case_id`, `owner_id`
- source type and encrypted object reference
- OCR/provider/version metadata
- raw candidate payload
- capture status: `uploaded | processing | needs_review | failed | resolved`
- field-level confidence and provenance
- retention and deletion state
- created/updated timestamps

A capture is not a verified product.

### ProductIdentity

Represents a stable, confirmed or explicitly unresolved product/formulation identity.

Fields:

- canonical parent concept
- exact ingredient identities
- chemical form, botanical species, part, extract/preparation, probiotic strain, or other applicable identity
- label amount, active/elemental amount, unit, serving basis
- formulation, route, release profile
- manufacturer, product name, identifier and version
- optional lot/batch and expiration
- identity status: `candidate | user_confirmed | expert_verified | unresolved | superseded`
- source capture and confirmation event
- identity fingerprint
- provenance and limitations

An exposure may reference only `user_confirmed` or `expert_verified` identity. Unknown fields stay unknown. Parent concepts do not lend all claims to children.

### RegimenVersion and RegimenItem

`RegimenVersion` is an immutable snapshot of the planned or reported regimen at a Case version.

`RegimenItem` contains:

- product identity
- intended amount, route, schedule, timing, start/stop
- purpose in the user's language
- reported versus verified status
- active/superseded state
- source event

Edits create a new version or append-only correction. They do not mutate historical exposure meaning.

### ExposureEvent

Represents what the user reports actually taking or doing.

Fields:

- Case, regimen item/product identity
- actual amount, unit, route
- occurred-at time and reporting time
- adherence relation to planned schedule
- source: user, import, device, researcher
- semantic `source_command_id`
- provenance, correction, and active state

Require a unique semantic key such as `(case_id, source_command_id)`. Repeated delivery returns the original event. Reuse of the same key with different meaning fails.

### ObservationEvent

Represents a reported or measured outcome/context.

Use a typed union:

- `reported`: value and unit/scale required
- `missed`: value forbidden
- `skipped`: value forbidden
- `unknown`: value forbidden
- `not_applicable`: value forbidden

Fields include concept, value, scale version, anatomical location, onset/offset, severity, source, occurred-at, reported-at, context, provenance, and correction.

Missing is never zero. A late observation preserves both occurrence and reporting time.

### ContextEvent

Captures predefined potential confounders such as meal composition, sleep, stress, activity, menstrual context, medication change, illness, rescue action, or environmental exposure.

The first slice supports only variables required by an approved experiment template. Do not create a universal lifestyle tracker.

### CandidateSignal

A hypothesis-generating relationship between one or more exposures and an outcome.

Fields:

- exposure and outcome concepts
- supporting windows/events
- contradictory events
- temporal ordering
- data completeness
- confounders
- discovery method and version
- status: `candidate | rejected | eligible_for_experiment | insufficient_data | superseded`
- allowed interpretation and limitations

Candidate signals never automatically become Case findings, recommendations, or causal conclusions.

### ExperimentProtocol

Fields:

- primary question and outcome
- exact eligible intervention
- design type and phase plan
- baseline, latency, washout/carryover assumptions
- measurement schedule
- adherence threshold
- confounders
- missing-data policy
- analysis version
- eligibility basis and safety review
- stop/escalation rules
- status: `draft | ineligible | needs_review | approved_for_uat | active | paused | stopped | complete | uninterpretable`
- product/research purpose
- protocol version and consent linkage

Activation is a governed transition. The LLM may draft only inside an approved template.

### ExperimentPhase and ProtocolEvent

Phases include baseline, intervention, withdrawal, or rechallenge only when allowed. Protocol events record check-ins, adherence, deviations, pause, stop, safety escalation, and completion.

Potentially serious prior reactions, unsafe withdrawal, essential medication changes, pregnancy-sensitive risks, or unclear structural contraindications fail closed or require approved professional supervision.

### AttributionAnalysis

A versioned deterministic analysis object:

- protocol and data cutoff
- method/version
- effect estimate and uncertainty
- adherence and missingness
- temporal-order result
- confounder assessment
- sensitivity analyses
- alternative explanations
- external-evidence applicability
- interpretation class: `consistent_signal | possible_signal | no_detectable_difference | possible_adverse_signal | inconclusive | invalid`
- allowed wording
- prohibited inference
- reviewer status

No single disease-probability or universal confidence score is permitted.

### PersonalEvidenceObject

The durable moat primitive. It links:

- exact question
- exact product/intervention identity
- protocol and phases
- exposures, observations, context, adherence, deviations
- safety events
- attribution analysis
- supporting evidence claims
- alternative explanations
- confidence dimensions
- user and expert corrections
- Case version and provenance

It is versioned and append-only. Passport entries are projections of accepted Personal Evidence Objects.

### PassportVersion

An immutable exportable snapshot with:

- consumer summary
- clinician brief
- machine-readable JSON
- source Case version
- Personal Evidence Object versions
- unresolved identity/data gaps
- safety limitations
- generation and review status

Regeneration creates a new version. Old shared versions remain traceable.

### ConsentPurpose and ResearchEligibility

Extend the existing consent work rather than creating a second consent service.

Purposes must distinguish:

- personal product use
- clinician sharing
- prospective research participation
- deidentified secondary analysis
- model improvement
- commercial communications

Withdrawing research consent synchronously blocks new research reads and commits. Asynchronous revocation jobs are cleanup, not the primary enforcement boundary. Product access remains unless separately withdrawn or deleted.

## 5. Shared event contract

Material events include:

- `product.capture.created`
- `product.identity.confirmed`
- `regimen.version.published`
- `exposure.recorded`
- `observation.recorded`
- `signal.generated`
- `experiment.drafted`
- `experiment.activated`
- `experiment.safety_stopped`
- `attribution.completed`
- `personal_evidence.accepted`
- `passport.published`
- `research_consent.withdrawn`

Every event contains:

- event ID
- aggregate ID
- aggregate version
- Case ID and Case version
- causation and correlation IDs
- schema version
- occurred-at and recorded-at
- actor/source category
- purpose/consent basis
- non-PHI operational classification

Use a transactional outbox. Consumers deduplicate by event ID and enforce aggregate ordering. Contradictory or unrecognized events quarantine visibly.

## 6. API architecture

Add one router under `/api/v1/personal-evidence`.

Representative resources:

- `POST /cases/{case_id}/product-captures`
- `GET /product-captures/{id}`
- `POST /product-identities/{id}/confirm`
- `GET /cases/{case_id}/regimen`
- `POST /cases/{case_id}/regimen-items`
- `POST /cases/{case_id}/exposures`
- `POST /cases/{case_id}/observations`
- `GET /cases/{case_id}/timeline`
- `POST /cases/{case_id}/signals:analyze`
- `GET /cases/{case_id}/signals`
- `POST /signals/{id}/experiment-drafts`
- `POST /experiments/{id}:activate`
- `POST /experiments/{id}/check-ins`
- `POST /experiments/{id}:pause`
- `POST /experiments/{id}:stop`
- `POST /experiments/{id}:analyze`
- `GET /cases/{case_id}/passport`
- `POST /cases/{case_id}/passport:publish`
- `GET /passport-versions/{id}/export`
- `POST /research-consent:withdraw`

Every mutation requires:

- authentication and owner/role authorization
- expected Case version
- idempotency key
- accepted consent purpose
- provenance
- audit event
- explicit error/partial state
- no PHI in operational telemetry

Version conflicts return a coherent conflict response and refreshed Case version. They do not silently overwrite.

## 7. AI authority

AI may:

- extract label fields and propose product candidates
- normalize user language into candidate concepts
- generate research queries
- propose candidate signals
- draft an experiment inside approved templates
- summarize permitted evidence
- verbalize deterministic analysis and limitations

AI may not independently:

- confirm product identity
- infer missing observation values
- decide serious safety eligibility
- approve unsafe withdrawal or rechallenge
- determine consent
- create causal conclusions
- accept evidence entitlement
- mutate production knowledge truth
- publish a Passport
- rank commerce inventory above scientific alternatives

Store model/provider/version, structured input fingerprint, output, validation result, and rejection reason without logging raw PHI.

## 8. Worker architecture

Use separate Celery queues or routing keys within the current worker deployment:

- `personal_evidence.identity`
- `personal_evidence.signals`
- `personal_evidence.attribution`
- `personal_evidence.passport`
- `personal_evidence.research_export`

Every task:

- accepts stable IDs, never full health payloads in broker metadata
- is idempotent
- rechecks ownership/purpose before read and before commit
- has bounded retries and dead-letter/quarantine behavior
- records non-PHI counters and latency
- cannot transform candidate output into accepted truth without a governor

## 9. External data seams

Initial public/accessible sources may include PubMed, Europe PMC, PubChem, RxNorm, ClinicalTrials.gov, USDA FoodData Central, openFDA, and available supplement-label sources.

External records are cached with retrieval time, source version, identifier, and license/usage constraints. Vendor outage produces an unresolved state, not a fabricated substitute.

Barcode/product APIs are candidate accelerators, not identity authorities. The exact supplement product catalog may become proprietary because public labels are incomplete and historically unstable.

## 10. Security and privacy

- Preserve existing encrypted storage and owner scoping.
- Treat label images, regimen, symptoms, research status, and Passport exports as sensitive health information.
- Never write real health text into logs, prompts stored in GitHub, fixtures, telemetry labels, or issue comments.
- Use synthetic fixtures.
- Apply purpose-bound authorization to research reads and writes.
- Audit material identity confirmation, experiment transition, analysis acceptance, Passport publication, sharing, consent change, and correction.
- Define retention and deletion before prospective research begins.
- Require Founder approval for production PHI, secondary use, new vendors, or research export.

## 11. Observability

Non-PHI signals include:

- product-capture processing latency
- ambiguous-field rate
- identity-confirmation abandonment
- idempotency dedupe and conflict counts
- illegal observation-union rejection
- exposure/observation lag
- Case projection mismatch count
- signal insufficiency/rejection rate
- experiment eligibility and stop reasons
- adherence and missingness aggregates under approved purpose
- attribution invalid/inconclusive rate
- Passport publication failures
- research authorization denials
- post-withdrawal job blocks
- agent certification expiration/block count

Tripwires:

- any mixed Case version rendered
- any missing observation stored as absence
- any duplicate semantic exposure
- any post-withdrawal research commit attempt
- any unconfirmed identity used in attribution
- any causal wording emitted for invalid/confounded analysis
- any serious safety fixture not escalated

## 12. Migration strategy

Do not modify existing discovery tables in the first documentation PR.

Implementation migrations proceed additively:

1. Add personal-evidence tables with foreign keys to `discovery_cases`, users, and patients.
2. Add explicit typed missingness before analysis.
3. Add product capture and identity confirmation.
4. Add regimen and exposure event tables with semantic idempotency.
5. Add experiment and analysis tables behind disabled flags.
6. Add Personal Evidence Object and Passport versions.
7. Add research-purpose controls only after approved consent ADR.

Never reinterpret existing zero values or inferred exposure history without provenance. Quarantine ambiguous legacy data.

Rollback disables feature entry points and workers while preserving append-only data. Do not down-migrate accepted corrections into ambiguous legacy representation.

## 13. Feature flags

- `PERSONAL_EVIDENCE_REGIMEN_V1`
- `PERSONAL_EVIDENCE_SIGNALS_V1`
- `PERSONAL_EVIDENCE_EXPERIMENTS_V1`
- `PERSONAL_EVIDENCE_ATTRIBUTION_V1`
- `PERSONAL_EVIDENCE_PASSPORT_V1`
- `PERSONAL_EVIDENCE_RESEARCH_MODE_V1`

Flags default off. Research mode and production behavior require separate Founder authorization.

## 14. Vertical slices

### Slice 0 — Agent-control and architecture

Documentation, certification registry, state machine, issue templates, qualification tests, and no health-data mutation.

### Slice 1 — Regimen truth

Upload/manual capture -> candidate extraction -> field-level uncertainty -> user confirmation -> immutable regimen version -> workspace display.

### Slice 2 — Exposure and observation truth

Record actual exposure -> typed check-in -> explicit missingness -> coherent Case timeline -> corrections.

### Slice 3 — One bounded experiment

One exact nonessential intervention -> baseline/introduction protocol -> eligibility/safety gate -> adherence -> pause/stop.

### Slice 4 — Attribution

Deterministic versioned analysis -> missingness/confounders -> sensitivity -> allowed wording -> Judge fixture.

### Slice 5 — Passport

Accepted Personal Evidence Object -> consumer and clinician projections -> immutable version -> share/export audit.

### Slice 6 — Research mode

Prospective protocol, purpose consent, study identifiers, approved metrics, deidentified export, revocation races, and operational feasibility.

## 15. Definition of done

A slice is complete only when:

- every acceptance claim maps to the real deployed route and a test
- hostile inputs fail safely and visibly
- Case/snapshot, identity, consent, and provenance remain coherent
- UI covers loading, empty, partial, uncertain, stale, denied, safety, error, correction, recovery, and success
- non-PHI observability and rollback exist
- implementation handoff names exact SHA and limitations
- Independent Judge approves the exact SHA
- UAT evidence exists
- Founder approves any RED boundary

The trap: a beautiful Passport can still be a false artifact if exact identity, missingness, temporal order, consent, or Case version is wrong.
