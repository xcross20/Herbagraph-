# ADR-0009: Founder Architecture Amendments to ADR-0008

- **Status:** Proposed
- **Date:** 2026-08-20
- **Amends:** ADR-0008 (`38cd524`)
- **Issue:** #65 successor
- **Decision owners:** Founder, Health AI Architecture
- **Independent review:** Required before acceptance; report SHA for review after this commit

---

## Context

ADR-0008 established the five-service Personal Evidence modular monolith boundary. Before Slice 1 implementation begins, the Founder issued four amendments that tighten the domain model in ways that affect schemas, projections, eligibility rules, and test inventory. These amendments are incorporated here as formal changes to ADR-0008 and are reflected in the architecture record in `PLATFORM_ARCHITECTURE.md`.

---

## Amendment 1 — Exposure Persistence Is Distinct from Attribution Eligibility

### Original constraint (ADR-0008, line ~160)

> An exposure may reference only `user_confirmed` or `expert_verified` identity.

### Problem

This constraint conflates two separate concerns:

1. **Recording what the user reported** — a historical, longitudinal truth requirement.
2. **Attributing an effect to an identified product** — a scientific eligibility requirement.

An exposure is a factual record of what happened. Product identity resolution is a separate epistemic process. Forcing unresolved product identity to block exposure recording would silently discard real longitudinal data and create gaps in personal history.

### Decision

**Exposure persistence requirement ≠ attribution eligibility requirement.**

`ExposureEvent` must accept references to `candidate`, `user_confirmed`, `expert_verified`, or explicitly `unresolved` product identity. The record must include:

- the `ProductCapture` reference or available product identifier;
- the known quantity, route, and timing;
- `occurred_at` and `reported_at`;
- source and provenance;
- an explicit `identity_resolution_status` field drawn from `ProductIdentity.identity_status`.

Known fields are recorded faithfully. Unknown fields are left null — do not fabricate unresolved fields.

### Attribution eligibility

An unresolved exposure **may** exist in longitudinal truth while being **ineligible** for the following downstream uses:

1. precise dose-response inference requiring exact strength;
2. ingredient-specific causal attribution;
3. interaction claims requiring exact formulation identity;
4. research-grade inclusion requiring exact product/formulation;
5. experiment activation when the protocol requires verified identity;
6. inclusion in attribution analyses where identity ambiguity is a confounder;
7. export in Personal Evidence Objects that make identity claims.

### Projection contract

- Regimen projections surface identity resolution status per item.
- Signal and experiment eligibility gates must check `identity_resolution_status` explicitly.
- Attribution analyses must declare identity completeness as a confidence dimension.
- Passport entries that assert intervention identity must reference a `user_confirmed` or `expert_verified` record or explicitly declare unresolved identity as a known limitation.

### Schema changes

`pe_exposure_events` gains:

- `identity_resolution_status` (`candidate | user_confirmed | expert_verified | unresolved`) — mirrors the referenced `ProductIdentity.identity_status` at time of recording; null if no identity record exists.
- `identity_confidence_override_reason` (optional text) — when identity is unresolved, the user's stated reason for recording anyway (e.g., "photographed before resolution", "product discontinued").

`pe_candidate_signals` gains:

- `identity_resolution_minimum` — the minimum identity status required for this signal to be meaningful (set at signal generation time).

`pe_experiment_protocols` gains:

- `identity_resolution_required` (boolean) — whether this protocol template requires `user_confirmed` or `expert_verified` intervention identity to activate.

`pe_attribution_analyses` gains:

- `identity_completeness` dimension in the confidence profile.

### Consequences

- Longitudinal exposure records are complete even when identity is partial.
- Eligibility logic must explicitly gate attribution uses, not existence.
- Downstream modules must handle unresolved identity states gracefully rather than failing on null.
- Corrections to product identity must invalidate downstream analyses that depended on the wrong identity without deleting the historical exposures themselves.

### Rejected alternatives

- **Fabricating identity fields from parent concepts.** Rejected because it creates false precision and undermines longitudinal truth.
- **Blocking unresolved exposures entirely.** Rejected because it silences real personal history and breaks the longitudinal Case contract.

---

## Amendment 2 — First-Class CaseObjective Domain Concept

### Original constraint (ADR-0008, RegimenItem)

Purpose was stored as free text on `RegimenItem` (`purpose in the user's language`). No structured model existed for the objective itself.

### Problem

Intervention reasoning — especially Regimen Intelligence and future Regimen Compiler — must distinguish:

- support for one objective from conflict with another;
- objective alignment from objective neutrality;
- "must avoid" constraints from "desired direction" goals.

Free text cannot support this reasoning reliably. Normalized concept codes are required for structured comparison.

### Decision

Add a first-class `CaseObjective` / `CaseObjectiveVersion` domain concept.

`CaseObjective` represents a personal health or wellness goal tied to a Case. It is versioned and append-only.

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `case_id` | FK | |
| `normalized_concept` | string | Derived from controlled vocabulary or expert mapping; not free text |
| `original_wording` | string | Preserved verbatim user language |
| `desired_direction` | enum | `increase`, `decrease`, `stabilize`, `avoid`, `improve` |
| `priority` | integer | 1 = highest; supports conflict resolution |
| `measurable_outcome` | JSONB | Optional structured goal (concept, scale, target, threshold, time_horizon) |
| `time_horizon` | string | Optional human-readable intent (e.g., "within 4 weeks") |
| `status` | enum | `active`, `superseded`, `abandoned` |
| `superseded_by` | FK | Reference to replacing `CaseObjectiveVersion` if superseded |
| `constraints` | JSONB | Optional "must avoid" objectives (e.g., avoid_daytime_sedation) |
| `provenance` | JSONB | Source command ID, actor, timestamp |
| `version` | integer | |
| `created_at` | datetime | |

**Examples:**

- `{ normalized_concept: "sleep_continuity", original_wording: "I want to stop waking up at 3am", desired_direction: "improve", priority: 1 }`
- `{ normalized_concept: "glucose_variability", original_wording: "My glucose spikes after carbs", desired_direction: "stabilize", priority: 2 }`
- `{ normalized_concept: "daytime_energy", desired_direction: "increase", priority: 1 }`
- `{ normalized_concept: "daytime_sedation", desired_direction: "avoid", priority: 1, constraints: { type: "must_avoid" } }`

**Relationship to RegimenItem:**

`RegimenItem` gains a `case_objective_id` FK. A regimen item may support zero, one, or many objectives. An objective may be pursued by zero, one, or many interventions simultaneously (which creates attribution ambiguity — see Hostile Case 5).

**RegimenItem purpose text** is preserved as `original_wording` on the linked `CaseObjective` or as `user_purpose_note` on the `RegimenItem` itself for ancillary purposes not elevated to formal objectives.

**Seam establishment only in Slice 1:**

Slice 1 establishes the data contracts and schema. Optimization — ranking interventions by objective support, detecting objective conflicts, or computing regimen-objective fit — is reserved for a future slice. Do not implement optimization unless required for schema compatibility.

### Consequences

- Objective reasoning has a structured, queryable seam.
- Conflicting objectives are detectable by the RegimenIntelligence service.
- Objective priority enables bounded conflict resolution without global optimization.
- Free-text purpose remains available for provenance but is not the primary reasoning surface.

---

## Amendment 3 — Regimen Intelligence Seam

### Problem

The current architecture distributes relationship reasoning across implicit module logic. There is no explicit domain service for regimen-level analysis. As intervention complexity grows, the system must reason over:

- product-product interactions;
- ingredient-ingredient interactions;
- ingredient-medication interactions;
- intervention-objective alignment;
- intervention-timing constraints;
- intervention-measurement confounding.

Treating "no documented interaction" as evidence of compatibility or safety is a scientific hazard.

### Decision

Reserve an explicit `RegimenIntelligence` domain service seam.

**Responsibility contract:**

The service must reason over relationships between:
- products (`ProductIdentity`);
- ingredients (elemental/extracted active components);
- medications (existing drug exposures);
- interventions (`RegimenItem`);
- objectives (`CaseObjective`);
- timing windows;
- measurements.

**Relationship taxonomy:**

Every documented or inferred relationship is classified using this taxonomy:

| Relationship | Code | Meaning |
|---|---|---|
| Complementary | `complementary` | Distinct mechanisms, no overlap, may combine |
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
| Unknown | `unknown` | Relationship not established; do not infer safe or compatible |
| No relationship documented | `no_documentation` | Absence of documentation; not equivalent to safe or compatible |

**Critical invariant:**

> Absence of a documented interaction MUST NOT be represented as compatibility or safety.

`no_documentation` is a relationship status, not a green signal. `unknown` is an explicit epistemic state that must be displayed as unknown.

**Authority boundary:**

`RegimenIntelligence` is a read/analysis service. It does not mutate regimen state. It produces relationship assessments and flags. It does not activate experiments, confirm identity, or publish Passport entries.

**Slice 1 scope:**

Do not build speculative synergy inference. Establish data contracts, relationship taxonomy, authority boundaries, and the minimal read seams. The service may surface known relationships from existing safety/evidence data and flag unresolved relationships for future documentation.

**Schema changes:**

`pe_regimen_intelligence_relationships`:

- `id`, `case_id`, `regimen_version_id`
- `entity_a_type` (`product`, `ingredient`, `intervention`, `medication`)
- `entity_a_id`
- `entity_b_type`
- `entity_b_id`
- `relationship` — one of the taxonomy codes above
- `confidence` — `established`, `plausible`, `speculative`, `unknown`
- `evidence_reference` — source citation or evidence claim ID if applicable
- `display_label` — human-readable summary
- `source` — `manual`, `automated`, `external_database`
- `created_at`, `updated_at`

`RegimenIntelligence` service:

```python
class RegimenIntelligence:
    def assess_regimen(self, regimen_version_id: UUID, case_id: UUID) -> RegimenAssessment:
        """Return relationship map, conflicts, attribution risks, and unresolved queries."""

    def query_relationship(
        self, entity_a: EntityRef, entity_b: EntityRef
    ) -> Relationship | NoDocumentation | Unknown:
        """Return the documented or inferred relationship between two entities."""

    def flag_conflicts(
        self, regimen_items: list[RegimenItem], objectives: list[CaseObjective]
    ) -> list[ObjectiveConflict | TimingConflict | MeasurementConfounding]:
        """Identify objective conflicts and measurement confounds in a regimen."""
```

### Consequences

- Regimen-level reasoning has an explicit authority boundary.
- No interaction status can silently default to "compatible."
- Future Regimen Compiler can consult the relationship map without owning interaction truth.
- Attribution risk from overlapping mechanisms is surfaceable at regimen review.

---

## Amendment 4 — RegimenCompiler Future Boundary

### Problem

A naive Regimen Compiler might rank individual interventions by some score and select the top-K as the "best regimen." This creates an opaque global optimum that has no scientific validity for personal evidence:

- Individually high-ranked interventions may conflict or interact.
- Simultaneous changes destroy attribution interpretability.
- Burden, timing, and measurability are not additive.
- "Best" for one objective may be worst for another.

### Decision

Reserve a future `RegimenCompiler` domain seam with explicit constraints.

**Purpose:**

`RegimenCompiler` transforms candidate intervention sets into a coherent regimen or experimental sequence, considering:

- objective alignment (support vs conflict);
- evidence strength;
- safety and interaction risks from `RegimenIntelligence`;
- complementarity and redundancy;
- intervention burden;
- timing constraints;
- measurability (clean attribution requires isolated changes);
- attribution loss from simultaneous changes.

**Prohibited patterns:**

- No opaque global "best regimen" score may become scientific truth.
- The compiler must never assume that individually high-ranked interventions form an optimal combination.
- No recommendation may be emitted without surfacing the conflicts, tradeoffs, and attribution risks of the proposed combination.

**Seam:**

```python
class RegimenCompiler:
    def compile(
        self,
        candidate_interventions: list[InterventionCandidate],
        objectives: list[CaseObjective],
        constraints: list[ObjectiveConstraint],
        intelligence_relationships: RegimenAssessment,
    ) -> CompilationResult:
        """
        Returns a proposed regimen sequence or parallel regimen with explicit tradeoffs.
        Does not auto-activate. Returns a reviewable proposal with attribution risk noted.
        """

@dataclass
class CompilationResult:
    proposed_items: list[RegimenItem]
    sequencing rationale: str
    simultaneous_change_count: int  # attribution risk indicator
    active_conflicts: list[ConflictFlag]
    unresolved_relationships: list[EntityRef]
    attribution_risk_summary: str
    burden_estimate: float
    measurability_score: float
    display_conflicts_and_tradeoffs: list[str]
```

**Slice 1 compatibility:**

This is a future implementation. Slice 1 establishes architecture compatibility only:

- `CaseObjective` schema supports constraint ("must avoid") and priority fields needed by the compiler.
- `RegimenIntelligence` relationship map provides the conflict and relationship data the compiler requires.
- `CompilationResult` data shape is reserved in the schema so future implementation does not require migration.
- No compiler logic is implemented in Slice 1.

### Consequences

- No combination score can become scientific truth before the seam exists.
- Future compiler implementation has a clear authority and output contract.
- Attribution risk from simultaneous changes is a first-class output dimension.

---

## Amendment 5 — Hostile Design and Test Cases

The following explicit design and test cases must be implemented to verify domain invariants. They are **hostile cases**: they describe failure modes and edge conditions, not the happy path.

### HC-1: Unresolved exposure preserved but blocked from attribution

**Setup:** A user photographs a supplement label at 08:15. OCR extracts product name and dose but cannot resolve exact extract strength. The user records the exposure anyway.

**Expected:**
- `ExposureEvent` is persisted with `identity_resolution_status = unresolved` and known fields populated.
- The exposure appears in the Case timeline with a visible "identity unresolved" indicator.
- The exposure does NOT appear in any `AttributionAnalysis` inputs.
- A `CandidateSignal` that includes this exposure is marked `insufficient_data` or `identity_resolution_minimum` violated.
- An `ExperimentProtocol` that requires `identity_resolution_required = True` cannot be activated with this intervention.

**Verification:** Test that `AttributionAnalysis` input query filters on `identity_resolution_status IN ('user_confirmed', 'expert_verified')` and excludes `unresolved`.

---

### HC-2: Ingredient-overlap warning from two branded products

**Setup:** User adds two separately branded products, each independently verified as `user_confirmed`, but both contain the same active ingredient (e.g., 500 mg zinc from different brands).

**Expected:**
- `RegimenIntelligence.query_relationship(product_a, product_b)` returns `redundant` or `pharm_overlap` (ingredient-level match).
- The regimen version shows an ingredient overlap warning.
- The overlap is visible in the regimen review UI.
- If both products are active simultaneously, `attribution_risk_summary` notes shared ingredient as a confounding factor.

**Verification:** Test that `RegimenIntelligence` performs ingredient-level normalization on confirmed products and detects overlap even when brand names differ.

---

### HC-3: Individual support + joint safety concern

**Setup:** Intervention A individually supports objective sleep_quality. Intervention B individually supports objective daytime_energy. Together, they produce a pharmacodynamic overlap on GABA pathways that creates daytime sedation.

**Expected:**
- `RegimenIntelligence` returns `complementary` for each individual intervention vs the objective.
- `RegimenIntelligence` returns `safety_conflict` or `pharm_overlap` for the pair.
- `RegimenCompiler.compile()` (future) surfaces the conflict in `active_conflicts`.
- The regimen review surfaces the joint concern before activation.
- The concern is NOT silenced because each intervention individually looks supportive.

**Verification:** Test that the intelligence relationship assessment is performed on the combination, not just on individual items.

---

### HC-4: Objective support + objective conflict

**Setup:** Intervention A supports `daytime_energy` (priority 1). Intervention B supports `avoid_daytime_sedation` (priority 1). Both are active simultaneously.

**Expected:**
- `RegimenIntelligence.flag_conflicts()` returns an `ObjectiveConflict` linking both objectives and both interventions.
- The conflict is surfaced in the regimen review with both objective wordings.
- Neither objective is secretly "outvoted" by a global score.
- The resolution requires explicit user or clinician choice, not algorithmic preference.

**Verification:** Test that flagging is based on `CaseObjective.priority` and `desired_direction`, not on intervention count.

---

### HC-5: Simultaneous start → low attribution interpretability

**Setup:** Five interventions are started on the same day.

**Expected:**
- Each `RegimenItem` has its own `started_at`.
- The regimen review surfaces that five simultaneous changes produce high attribution ambiguity.
- `attribution_risk_summary` for any analysis including these exposures flags `simultaneous_change_count: 5`.
- `measurement_confounding` is raised for the regimen as a whole.
- The system does NOT suggest a combined attribution analysis as if it were a single-intervention result.

**Verification:** Test that `RegimenCompiler` (or the intelligence layer) computes `simultaneous_change_count` per analysis window and surfaces it in the attribution risk output.

---

### HC-6: Unknown interaction displayed as unknown, not safe

**Setup:** A new intervention is added. Its ingredient has no documented relationship with an existing medication in the evidence base.

**Expected:**
- `RegimenIntelligence.query_relationship(new_ingredient, existing_medication)` returns `unknown` (not `no_documentation` masquerading as safe).
- The regimen review displays "Unknown interaction — insufficient evidence to assess" prominently.
- The status is NOT green, not neutral, not silently omitted.
- A user or clinician sees the epistemic gap, not false reassurance.

**Verification:** Test that the relationship display logic renders `unknown` as an amber "insufficient data" state and renders `no_documentation` as distinct from "compatible."

---

### HC-7: Product identity correction invalidates analyses, preserves exposures

**Setup:** User records an exposure attributed to `ProductIdentity` P1. Later, P1 is corrected to `ProductIdentity` P2 (different active ingredient). P1's exposures still occurred.

**Expected:**
- The historical `ExposureEvent` records are NOT deleted.
- `ExposureEvent` fields (amount, timing, route) remain intact.
- `ExposureEvent.product_identity_id` is updated to reference P2 (or to `unresolved` if P2 is also uncertain).
- Any `AttributionAnalysis` that used P1 as a primary intervention is marked `invalid` or `superseded`.
- `CandidateSignal` records that referenced P1 exposures in their inputs are flagged for review.
- The corrected regimen version reflects P2 going forward.
- The Case timeline shows the correction event without erasing historical entries.

**Verification:** Test that `ProductIdentity` correction triggers analysis invalidation workflow but not exposure deletion. Test that the correction event is auditable and timestamped.

---

### HC-8: Stopping intervention changes projection, preserves history

**Setup:** An active `RegimenItem` is stopped (user reports discontinuation). The exposure history up to the stop date is preserved.

**Expected:**
- `RegimenItem.status` transitions to `superseded` with a `stopped_at` timestamp.
- Historical `ExposureEvent` records before `stopped_at` are preserved and unchanged.
- The current regimen version (for projections) does not include the stopped item.
- A corrected `AttributionAnalysis` that included data from the active period remains valid.
- The Passport entry for this intervention reflects the active period and the reason for stopping (if provided).
- The Case timeline shows the stop event.

**Verification:** Test that stopping does not delete exposures. Test that regimen projection excludes stopped items while preserving historical exposure records.

---

## Summary of Changes to ADR-0008

| Section | Change |
|---|---|
| ExposureEvent eligibility | Removed "only `user_confirmed` or `expert_verified`" constraint; exposure persistence is now independent of attribution eligibility |
| ProductIdentity | Confirmed: `unresolved` status is valid for exposure recording; explicitly disallowed for attribution uses |
| CandidateSignal | Added `identity_resolution_minimum` field |
| ExperimentProtocol | Added `identity_resolution_required` boolean |
| AttributionAnalysis | Added `identity_completeness` confidence dimension |
| Domain concepts | Added first-class `CaseObjective` |
| RegimenItem | Gained `case_objective_id` FK; purpose text is now provenance for `CaseObjective` |
| Domain seams | Added `RegimenIntelligence` service with relationship taxonomy |
| Future boundary | Added `RegimenCompiler` seam with prohibited patterns |
| Schema additions | `pe_exposure_events.identity_resolution_status`, `pe_regimen_intelligence_relationships`, `CompilationResult` data shape |
| Hostile cases | Added 8 explicit design/test cases HC-1 through HC-8 |

---

## Acceptance Evidence

This amendment is accepted when:

- [ ] ADR-0009 is committed to `architect/65-amendments` with SHA reported for Independent Judge review
- [ ] `PLATFORM_ARCHITECTURE.md` reflects all four amendments and eight hostile cases
- [ ] Schema additions (identity_resolution_status, CaseObjective, RegimenIntelligence relationships) are reflected in the architecture doc
- [ ] Slice 1 implementation scope does NOT include: optimization, Regimen Compiler logic, causal attribution, Signals activation, experiment activation, or research mode
- [ ] Independent Judge returns PASS on the amended architecture record
- [ ] Founder authorizes Slice 1 implementation from the amended architecture SHA
