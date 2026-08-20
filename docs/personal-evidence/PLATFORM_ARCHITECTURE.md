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
    intake.py            # IntakeSession, IntakeResponse, IntakeObjective
    regimen.py           # RegimenVersion, RegimenItem, relationship semantics
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

### IntakeSession

> **IntakeSession — Structured personal intake upstream of Regimen Truth.** An IntakeSession captures the user's current supplement and medication regimen, their health objectives, and their preferences before any product identity is resolved. It is the structured input surface that feeds Regimen Truth. IntakeSessions are read-only once submitted; corrections create new sessions or amendment events.

**Purpose:** "Tell me what you take and what you're trying to achieve."

An IntakeSession represents one intake conversation or form submission. It is NOT the same as a Discovery Case turn — it is a purpose-specific bounded session for regimen entry. Multiple IntakeSessions may occur over a Case's lifetime (e.g., initial intake, annual refresh, new objective added).

**Fields:**

- `id`, `case_id`, `owner_id`
- `status`: `draft | active | submitted | superseded`
- `purpose`: `initial | refresh | objective_added | correction`
- `started_at`, `submitted_at`
- `case_objective_ids`: ordered list of `CaseObjective` IDs created or linked by this session
- `source_command_id`: semantic idempotency key
- `provenance`, `created_at`, `updated_at`

**IntakeResponse** (child of IntakeSession):

Represents one answered intake question.

Fields:

- `id`, `intake_session_id`
- `concept`: normalized intake concept (e.g., `supplement`, `medication`, `frequency`, `route`, `dose_unit`)
- `raw_value`: user's raw text or number (preserved verbatim)
- `normalized_value`: parsed structured value where determinable (e.g., `2`, `twice_daily`)
- `unit`: e.g., `mg`, `capsule`, `drop`
- `confidence`: `certain | estimated | uncertain`
- `product_name_raw`: self-reported product name
- `brand_raw`: self-reported brand (may be null)
- `notes`: user's free-text notes
- `position`: ordering within the session
- `source_command_id`
- `created_at`

**IntakeObjective** (child of IntakeSession):

Represents one health objective surfaced during intake.

Fields:

- `id`, `intake_session_id`
- `original_wording`: verbatim user language
- `normalized_concept`: derived from controlled vocabulary or expert mapping
- `desired_direction`: `increase | decrease | stabilize | avoid | improve`
- `priority` (1 = highest)
- `measurable_outcome` (JSONB, optional): concept, scale, target, threshold, time_horizon
- `time_horizon`: human-readable intent (e.g., "within 4 weeks")
- `constraints` (JSONB, optional): "must avoid" objectives linked to this goal
- `status`: `proposed | confirmed | declined`
- `linked_case_objective_id`: FK to the `CaseObjective` created from this intake objective (populated on submit)
- `created_at`

**IntakeToRegimen flow:**

1. User completes IntakeSession → submits.
2. System parses `IntakeResponse` records into proposed `RegimenItem` drafts.
3. Product identity candidates are generated from `product_name_raw` via `ProductCapture` workers.
4. User reviews proposed `RegimenItem` drafts, confirms or corrects each.
5. Identity confirmation creates or links `ProductIdentity` records.
6. Confirmed items are published as a `RegimenVersion`.
7. `IntakeObjective` records with `status = confirmed` create `CaseObjective` records.
8. The `IntakeSession.submitted_at` and `linked_regimen_version_id` are recorded for audit.

**Key invariants:**

- An IntakeSession may reference products by self-reported name before identity is confirmed.
- `IntakeResponse.product_name_raw` is NOT the same as `ProductIdentity.product_name` — it is the user's raw input.
- IntakeSessions are immutable after submission. Corrections create a new session or an `IntakeAmendment` event.
- A submitted IntakeSession may not be deleted if it has been used to create a RegimenVersion.
- IntakeSession does NOT perform exposure recording — that is the job of `ExposureEvent`.

**Scope in Regimen Truth slice:** IntakeSession and IntakeResponse are implemented. IntakeObjective (linked to CaseObjective) is in scope for Regimen Truth since objectives are needed for regimen purpose attribution. Optimization of regimen recommendations is out of scope for Slice 1.

See ADR-0010.

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

> **Amendment 1 — Exposure persistence ≠ attribution eligibility.** An `ExposureEvent` may reference any `ProductIdentity` status including `unresolved`. The record must include the `identity_resolution_status` field drawn from the referenced `ProductIdentity`. Known fields are recorded faithfully; unknown fields are left null — do not fabricate unresolved fields. An exposure with `unresolved` identity is valid longitudinal truth but is **ineligible** for: precise dose-response inference, ingredient-specific causal attribution, interaction claims requiring exact formulation, research-grade inclusion, experiment activation requiring verified identity, attribution analyses where identity ambiguity is a confounder, and Passport entries asserting identity claims. See ADR-0009 Amendment 1 for the full invariant and schema additions.

### RegimenVersion and RegimenItem

`RegimenVersion` is an immutable snapshot of the planned or reported regimen at a Case version.

**RegimenVersion fields:**

- `id`, `case_id`, `owner_id`
- `version_number`: monotonically increasing per Case
- `status`: `draft | published | superseded`
- `source_intake_session_id`: FK to `IntakeSession` that produced this version (null if manually edited)
- `case_objective_ids`: objectives this regimen version is intended to serve
- `published_at`
- `case_version` at time of publication
- `provenance`, `created_at`

**RegimenItem** fields:

- `id`, `regimen_version_id`, `case_id`
- `product_identity_id` (FK, may be null for draft items with unresolved identity)
- `product_capture_id` (FK, source capture; may be null for manual entries)
- `intake_response_id` (FK, source `IntakeResponse` if derived from intake)
- `product_name_raw`: the self-reported name at time of capture
- `intended_amount`, `intended_unit`
- `serving_basis`: e.g., `per capsule`, `per teaspoon`, `per drop`
- `route`: `oral | topical | sublingual | transdermal | other`
- `schedule`: e.g., `twice_daily`, `with_meals`, `at_bedtime`
- `timing_notes`: free-text timing guidance
- `start_date`, `stop_date`, `stop_reason`
- `case_objective_id` (FK): the primary `CaseObjective` this item serves
- `user_purpose_note`: free-text purpose when not linked to a formal `CaseObjective`
- `identity_status_at_capture`: snapshot of `ProductIdentity.identity_status` at time of item creation
- `identity_resolution_status`: current resolution status (may improve after confirmation)
- `reported_vs_verified`: `reported | partially_verified | fully_verified`
- `status`: `draft | proposed | confirmed | active | superseded | stopped`
- `supersedes_item_id`: FK to the `RegimenItem` this one replaces
- `stop_reason`: `user_stopped | adverse_reaction | objective_met | replaced | product_discontinued | other`
- `source_command_id`
- `provenance`, `created_at`, `updated_at`

**Relationship semantics:**

- **Ingredient-level identity**: Two `RegimenItem` records with different `product_identity_id` values may still share active ingredients at the elemental level. `RegimenIntelligence` must normalize to ingredient level for overlap detection (see Amendment 3).
- **Objective linkage**: `RegimenItem.case_objective_id` links the item to its primary objective. Multiple items may serve the same objective (creating attribution ambiguity — see HC-5). An item may serve zero objectives (general wellness use).
- **Identity confidence**: `RegimenItem.reported_vs_verified` distinguishes items confirmed against a `ProductCapture` from those entered manually. This is orthogonal to `identity_resolution_status` — a manually entered item may have `user_confirmed` status if the user verified it without a capture.
- **Capture provenance**: `RegimenItem.intake_response_id` links back to the source `IntakeResponse` for audit. If the intake is corrected, the `RegimenItem` is superseded, not deleted.
- **Stop vs. supersession**: Stopping an item (user discontinued) is different from superseding (item was replaced by a corrected version). Stop preserves the item with `status = stopped`; supersession creates a new item and marks the old `superseded`.

**Editing rules:**

- All edits create a new `RegimenVersion` or append-only corrections within the current version.
- Corrections to `ProductIdentity` do NOT automatically update `RegimenItem.product_identity_id` — they trigger an analysis invalidation workflow. The user must confirm or correct the link.
- `RegimenVersion` is immutable once published. Corrections create a new version.

See ADR-0009 Amendment 3 (RegimenIntelligence), Amendment 4 (RegimenCompiler), and HC-2, HC-3, HC-4, HC-5.

### ExposureEvent

Represents what the user reports actually taking or doing.

Fields:

- Case, regimen item/product identity
- actual amount, unit, route
- `identity_resolution_status`: mirrors the referenced `ProductIdentity.identity_status` (`candidate | user_confirmed | expert_verified | unresolved`) at time of recording; null if no identity record exists
- `identity_confidence_override_reason` (optional): when identity is unresolved, the user's stated reason for recording anyway
- occurred-at time and reporting time
- adherence relation to planned schedule
- source: user, import, device, researcher
- semantic `source_command_id`
- provenance, correction, and active state

> **Amendment 1 — Longitudinal truth is independent of attribution eligibility.** An `ExposureEvent` is a factual record of what the user reported. It is persisted to maintain complete personal history even when product/formulation identity remains unresolved. Downstream modules (signals, experiments, attribution, passport) must explicitly gate their eligibility on `identity_resolution_status`. Corrections to `ProductIdentity` invalidate dependent analyses without deleting historical exposures. See ADR-0009 Amendment 1 HC-7 and HC-8.

### CaseObjective

> **Amendment 2 — First-class objectives.** Purpose is no longer stored as free text alone on `RegimenItem`. A structured `CaseObjective` concept is established to support objective-aligned intervention reasoning.

Represents a personal health or wellness goal tied to a Case. It is versioned and append-only.

Fields:

- `id`, `case_id`, `case_objective_version_id`
- `normalized_concept`: derived from controlled vocabulary or expert mapping; not free text
- `original_wording`: preserved verbatim user language
- `desired_direction`: `increase | decrease | stabilize | avoid | improve`
- `priority`: integer, 1 = highest; supports conflict resolution
- `measurable_outcome` (JSONB): optional structured goal (concept, scale, target, threshold, time_horizon)
- `time_horizon`: optional human-readable intent (e.g., "within 4 weeks")
- `status`: `active | superseded | abandoned`
- `superseded_by`: FK to replacing `CaseObjectiveVersion`
- `constraints` (JSONB): optional "must avoid" objectives (e.g., `{ type: "must_avoid", concept: "daytime_sedation" }`)
- `provenance`: source command ID, actor, timestamp
- `version`, `created_at`

Examples:
- `{ normalized_concept: "sleep_continuity", original_wording: "I want to stop waking up at 3am", desired_direction: "improve", priority: 1 }`
- `{ normalized_concept: "glucose_variability", desired_direction: "stabilize", priority: 2 }`
- `{ normalized_concept: "daytime_energy", desired_direction: "increase", priority: 1 }`
- `{ normalized_concept: "daytime_sedation", desired_direction: "avoid", priority: 1, constraints: { type: "must_avoid" } }`

**Relationship to RegimenItem:** `RegimenItem` gains `case_objective_id` FK. A regimen item may support zero, one, or many objectives. An objective may be pursued by zero, one, or many interventions simultaneously (creating attribution ambiguity — see HC-5).

**RegimenItem purpose text** is preserved as provenance for the linked `CaseObjective` or as `user_purpose_note` on `RegimenItem` for ancillary purposes not elevated to formal objectives.

**Slice 1 scope:** Schema and data contracts only. Optimization — ranking interventions by objective support or detecting objective conflicts — is reserved for a future slice.

See ADR-0009 Amendment 2.

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
- `identity_resolution_minimum`: the minimum `identity_resolution_status` required for this signal to be meaningful (set at signal generation time; unresolved exposures with lower status are excluded from supporting windows)
- status: `candidate | rejected | eligible_for_experiment | insufficient_data | superseded`
- allowed interpretation and limitations

Candidate signals never automatically become Case findings, recommendations, or causal conclusions.

### ExperimentProtocol

Fields:

- primary question and outcome
- exact eligible intervention
- `identity_resolution_required` (boolean): whether this protocol template requires `user_confirmed` or `expert_verified` intervention identity to activate; unresolved exposures are ineligible
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
- `identity_completeness` (confidence dimension): whether all primary intervention exposures have `user_confirmed` or `expert_verified` identity; unresolved identity is a documented confounder
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

### RegimenIntelligence

> **Amendment 3 — Regimen Intelligence seam.** An explicit domain service for regimen-level relationship analysis is established. This separates relationship reasoning from individual module logic and prevents "no documented interaction" from being treated as a safe or compatible signal.

**Responsibility:** `RegimenIntelligence` reasons over relationships between products, ingredients, medications, interventions, objectives, timing, and measurements. It is a read/analysis service — it does not mutate regimen state, activate experiments, confirm identity, or publish Passport entries.

**Authority boundary:** The service produces relationship assessments and flags. It does not create clinical conclusions or recommendations.

**Relationship taxonomy:**

| Relationship | Code | Meaning |
|---|---|---|
| Complementary | `complementary` | Distinct mechanisms; may combine |
| Potential synergy | `potential_synergy` | Mechanistically plausible enhanced combined effect; unconfirmed |
| Redundant | `redundant` | Same active ingredient or mechanism; unnecessary duplication |
| Pharmacodynamic overlap | `pharm_overlap` | Same receptor/pathway/mechanism; risk of additive effect |
| Pharmacokinetic interaction | `pk_interaction` | Absorption, distribution, metabolism, or excretion alteration |
| Absorption interaction | `absorption_interaction` | Specific GI-binding, chelation, or bioavailability change |
| Antagonistic | `antagonistic` | Known opposing mechanisms |
| Safety conflict | `safety_conflict` | Known or plausible adverse interaction |
| Objective conflict | `objective_conflict` | One intervention supports an objective while another conflicts with it |
| Timing conflict | `timing_conflict` | Scheduling or temporal requirements cannot coexist |
| Measurement confounding | `measurement_confounding` | Combined use prevents clean measurement of either effect |
| Unknown | `unknown` | Relationship not established; must be displayed as unknown, not safe |
| No relationship documented | `no_documentation` | Absence of documentation; not equivalent to compatible or safe |

**Critical invariant:** Absence of a documented interaction MUST NOT be represented as compatibility or safety. `unknown` and `no_documentation` are explicit epistemic states rendered as such in the UI.

**Schema:** `pe_regimen_intelligence_relationships` — `id`, `case_id`, `regimen_version_id`, `entity_a_type`, `entity_a_id`, `entity_b_type`, `entity_b_id`, `relationship` (taxonomy code), `confidence` (`established | plausible | speculative | unknown`), `evidence_reference`, `display_label`, `source` (`manual | automated | external_database`), timestamps.

**Slice 1 scope:** Establish data contracts and relationship taxonomy. Surface known relationships from existing safety/evidence data. Flag unresolved relationships for future documentation. Do not build speculative synergy inference.

**Service shape (reserved):**

```python
class RegimenIntelligence:
    def assess_regimen(self, regimen_version_id: UUID, case_id: UUID) -> RegimenAssessment: ...
    def query_relationship(self, entity_a: EntityRef, entity_b: EntityRef) -> Relationship: ...
    def flag_conflicts(self, regimen_items: list[RegimenItem], objectives: list[CaseObjective]) -> list[ObjectiveConflict | TimingConflict | MeasurementConfounding]: ...
```

See ADR-0009 Amendment 3 and HC-2, HC-3, HC-4, HC-6.

### RegimenCompiler (Future Boundary)

> **Amendment 4 — RegimenCompiler future boundary.** A future `RegimenCompiler` domain seam is reserved. Its purpose is to transform candidate intervention sets into a coherent regimen or experimental sequence. An opaque global "best regimen" score may not become scientific truth.

**Purpose:** Transform candidate intervention sets into a coherent regimen or experimental sequence considering: objective alignment, evidence strength, safety and interaction risks from `RegimenIntelligence`, complementarity and redundancy, intervention burden, timing constraints, measurability, and attribution loss from simultaneous changes.

**Prohibited patterns:**
- No opaque global "best regimen" score may become scientific truth.
- The compiler must never assume that individually high-ranked interventions form an optimal combination.
- No recommendation may be emitted without surfacing conflicts, tradeoffs, and attribution risks.

**Reserved data shape (`CompilationResult`):**

```python
@dataclass
class CompilationResult:
    proposed_items: list[RegimenItem]
    sequencing_rationale: str
    simultaneous_change_count: int       # attribution risk indicator
    active_conflicts: list[ConflictFlag]
    unresolved_relationships: list[EntityRef]
    attribution_risk_summary: str
    burden_estimate: float
    measurability_score: float
    display_conflicts_and_tradeoffs: list[str]
```

**Slice 1 scope:** Architecture compatibility only. `CaseObjective` schema, `RegimenIntelligence` relationship map, and `CompilationResult` data shape are established so future implementation does not require schema migration. No compiler logic is implemented.

See ADR-0009 Amendment 4.

## 5. Shared event contract

Material events include:

- `intake.session.started`
- `intake.session.submitted`
- `intake.objective.confirmed`
- `product.capture.created`
- `product.identity.confirmed`
- `regimen.version.published`
- `regimen.item.stopped`
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

- `POST /cases/{case_id}/intake-sessions`
- `GET /intake-sessions/{id}`
- `POST /intake-sessions/{id}/responses`
- `POST /intake-sessions/{id}/submit`
- `POST /cases/{case_id}/product-captures`
- `GET /product-captures/{id}`
- `POST /product-identities/{id}/confirm`
- `GET /cases/{case_id}/regimen`
- `POST /cases/{case_id}/regimen-items`
- `POST /cases/{case_id}/regimen-items/{id}/stop`
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

- intake-session abandonment rate
- intake-to-regimen conversion rate
- intake-response confidence distribution
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

### Slice 1 — Intake and Regimen Truth

**Intake flow:** IntakeSession -> IntakeResponse parsing -> proposed RegimenItem drafts -> user review -> product identity capture/confirmation -> RegimenVersion publication -> workspace projection.

**Regimen flow:** ProductCapture/OCR -> candidate extraction -> field-level uncertainty -> user confirmation -> immutable regimen version -> correction -> coherent workspace/Ask projection.

**Scope:** IntakeSession, IntakeResponse, IntakeObjective, CaseObjective (from IntakeObjective), ProductCapture, ProductIdentity, RegimenVersion, RegimenItem, correction workflows.

**Out of scope for Slice 1:** Signals, Experiments, Attribution, Passport, wearable ingestion, RegimenIntelligence optimization, RegimenCompiler, agent-control infrastructure, experiment activation, research mode.

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

## 14. Hostile Design Cases

> **Amendment 5 — Explicit hostile cases.** The following design and test cases verify domain invariants under adverse conditions. Each describes a failure mode, not the happy path. Implementations must demonstrate correct behavior before Slice acceptance.

### HC-1: Unresolved exposure preserved but blocked from attribution

An exposure with unresolved product identity is persisted to the Case timeline with full known fields and `identity_resolution_status = unresolved`. Downstream modules exclude it from attribution analyses and mark signals that depend on it as `insufficient_data`.

**Invariant tested:** Exposure persistence ≠ attribution eligibility.

### HC-2: Ingredient-overlap warning from two separately branded products

Two independently `user_confirmed` branded products both contain the same active ingredient (e.g., zinc from different brands). `RegimenIntelligence.query_relationship(product_a, product_b)` returns `redundant` or `pharm_overlap`. The regimen review shows a visible ingredient overlap warning.

**Invariant tested:** Ingredient-level normalization detects overlap even when brand names differ.

### HC-3: Individual support + joint safety concern

Intervention A individually supports objective sleep_quality. Intervention B individually supports objective daytime_energy. Together they produce pharmacodynamic overlap on GABA pathways creating daytime sedation. `RegimenIntelligence` returns `complementary` for each individual item vs objectives but `safety_conflict` or `pharm_overlap` for the pair.

**Invariant tested:** Relationship assessment is performed on the combination, not just individual items.

### HC-4: Objective support + objective conflict

Intervention A supports `daytime_energy` (priority 1). Intervention B supports `avoid_daytime_sedation` (priority 1). Both are active. `RegimenIntelligence.flag_conflicts()` returns an `ObjectiveConflict` surfaced in the regimen review. Neither objective is secretly "outvoted" by a count or score.

**Invariant tested:** Objective conflict flagging uses `CaseObjective.priority` and `desired_direction`, not intervention count.

### HC-5: Five simultaneous starts → low attribution interpretability

Five interventions start on the same day. `simultaneous_change_count = 5` is surfaced in the attribution risk summary. `measurement_confounding` is raised for the regimen as a whole. The system does not suggest a combined attribution analysis as if it were a single-intervention result.

**Invariant tested:** `RegimenIntelligence` or `RegimenCompiler` computes simultaneous change count per analysis window.

### HC-6: Unknown interaction displayed as unknown, not safe

A new intervention's ingredient has no documented relationship with an existing medication. `RegimenIntelligence.query_relationship()` returns `unknown`. The regimen review displays "Unknown interaction — insufficient evidence to assess." The status is NOT green or neutral. `unknown` and `no_documentation` are distinct epistemic states rendered as such.

**Invariant tested:** Absence of documentation ≠ compatible or safe.

### HC-7: Product identity correction invalidates analyses, preserves exposures

`ProductIdentity` P1 is corrected to P2 (different active ingredient). Historical `ExposureEvent` records are NOT deleted. Their `product_identity_id` is updated to reference P2 or set to `unresolved` if P2 is also uncertain. Any `AttributionAnalysis` that used P1 as a primary intervention is marked `invalid` or `superseded`. `CandidateSignal` records that referenced P1 exposures are flagged for review. The correction event is auditable and timestamped.

**Invariant tested:** Identity correction triggers analysis invalidation workflow without erasing historical exposures.

### HC-8: Stopping intervention changes projection, preserves history

A `RegimenItem` is stopped. `RegimenItem.status` transitions to `superseded` with `stopped_at`. Historical `ExposureEvent` records before `stopped_at` are preserved unchanged. The current regimen projection excludes the stopped item. `AttributionAnalysis` that included data from the active period remains valid. The Passport entry reflects the active period and stopping reason (if provided).

**Invariant tested:** Stopping does not delete exposures. Regimen projection excludes stopped items.

See ADR-0009 Amendment 5 for full specification of all eight cases.

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
