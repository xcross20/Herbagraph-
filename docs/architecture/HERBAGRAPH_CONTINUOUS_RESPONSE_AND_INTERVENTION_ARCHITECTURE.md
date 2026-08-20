# HerbaGraph Continuous Response and Intervention Architecture

**Status:** Founder-directed architecture specification  
**Audience:** Founder, Architect, Grok/Implementer, research collaborators, clinical/scientific reviewers  
**Branch:** `architect/continuous-response-architecture`  
**Relationship to existing architecture:** Additive. This specification extends the existing Case, Discovery, Investigation, Evidence, Intervention, and Monitoring loop. It does not replace the Discovery Engine, lab engine, safety engine, or evidence-confidence engine.

---

## 1. Executive thesis

HerbaGraph should evolve from a system that recommends or discusses evidence-supported interventions into a system that can **observe, structure, and learn from intervention response over time**.

The long-term product loop becomes:

> CONCERN → DISCOVERY → INVESTIGATION → EVIDENCE → INTERVENTION PLAN → EXPOSURE CAPTURE → CONTINUOUS RESPONSE → ATTRIBUTION ANALYSIS → UPDATED CASE → NEXT EXPERIMENT

The scientific goal is not to claim that a wearable can directly determine whether an herb “worked.” The system should instead capture a **multimodal biological response phenotype** and compare it against a person's baseline, intervention timing, competing exposures, confounders, safety constraints, and stated objectives.

The platform should support existing wearables first, then richer biosensors later. Hardware is replaceable. The durable HerbaGraph asset is the longitudinal intervention-response model, provenance structure, interaction graph, causal discipline, and accumulated responder-pattern dataset.

This architecture must support real-world use where people:

- take multiple herbs and supplements in the same day;
- take products containing multiple ingredients;
- change doses over time;
- skip doses or take them late;
- combine interventions intentionally;
- combine interventions unintentionally;
- pursue multiple objectives simultaneously;
- use interventions that reinforce the same objective;
- use interventions that antagonize each other;
- use interventions that help one objective but harm another;
- take medications, foods, caffeine, alcohol, and other exposures that confound interpretation;
- change sleep, diet, exercise, stress, or other behaviors at the same time;
- experience delayed, cumulative, or nonlinear responses.

Therefore the core primitive is not “user takes herb X.” The core primitive is a **time-bounded exposure with identity, amount, formulation, context, provenance, and uncertainty**.

---

## 2. Product positioning

HerbaGraph should not become a generic supplement tracker.

The system should answer progressively deeper questions:

1. **What is the person taking?**
2. **When, how much, and in what formulation?**
3. **What biological objectives or investigation branches is each intervention intended to affect?**
4. **Which interventions have overlapping mechanisms?**
5. **Which combinations may be complementary, redundant, antagonistic, or unsafe?**
6. **What physiological and subjective changes occur after exposure?**
7. **How confidently can those changes be associated with a single ingredient, a combination, or an uncontrolled confounder?**
8. **What should be kept stable, changed, stopped, separated, or tested next?**

The long-term differentiated product is a **biological experimentation operating system** for natural-product and multimodal interventions.

---

## 3. Updated architectural layers

### Layer 1 — Longitudinal Case

The Case remains the durable source of truth.

It stores:

- concerns;
- findings;
- investigation branches;
- evidence;
- tests;
- safety state;
- intervention plans;
- actual exposure events;
- regimen states;
- wearable observations;
- lab observations;
- symptoms and patient-reported outcomes;
- confounders;
- response analyses;
- attribution claims;
- corrections;
- experiment phases;
- outcome summaries.

Chat remains an interface over the Case.

### Layer 2 — Guided Discovery

Guided Discovery determines what additional information is useful and routes toward investigation, evidence gathering, intervention synthesis, or monitoring.

### Layer 3 — Investigation Map

The Investigation Map remains a coverage-aware representation of unresolved questions. Intervention response may update evidence or monitoring state but must not silently convert response into diagnosis or disease probability.

### Layer 4 — Evidence and Knowledge Graph

The graph should represent:

- biomarkers;
- pathways;
- mechanisms;
- botanicals;
- botanical constituents;
- nutrients;
- medications where supported;
- interventions;
- targets;
- physiological outcomes;
- adverse effects;
- contraindications;
- interactions;
- formulation properties;
- evidence claims;
- source provenance;
- objectives.

### Layer 5 — Intervention Synthesis

This layer generates evidence-constrained options tied to:

- objective;
- rationale;
- expected target;
- expected response window;
- uncertainties;
- safety conditions;
- monitoring plan;
- stopping rules;
- alternatives.

### Layer 6 — Exposure Ledger

New canonical subsystem.

The Exposure Ledger records what the person actually took or experienced, independent of what was planned.

### Layer 7 — Regimen Graph

New canonical subsystem.

The Regimen Graph computes the active combination of interventions and classifies relationships among them.

### Layer 8 — Continuous Observation Layer

Ingests wearable, CGM, mobile, lab, symptom, and eventually biosensor data.

### Layer 9 — Response Engine

Detects temporal changes relative to personal baseline and experiment phase.

### Layer 10 — Attribution and Experiment Engine

Estimates whether a response is consistent with:

- a single intervention;
- a combination;
- a delayed cumulative effect;
- an unrelated change;
- insufficiently controlled data.

It must preserve uncertainty and avoid causal overclaiming.

### Layer 11 — Learning Network

Aggregates consented, governed, de-identified intervention-response structures to identify responder patterns, interaction hypotheses, monitoring targets, and better experimental designs.

---

## 4. Canonical intervention model

HerbaGraph must distinguish the following entities.

### 4.1 Intervention Concept

A normalized conceptual intervention.

Examples:

- Ashwagandha
- Berberine
- Magnesium glycinate
- Curcumin
- Resistance training
- Low-FODMAP diet

Fields should include:

- `intervention_concept_id`
- canonical name
- intervention class
- botanical taxonomy where relevant
- constituent relationships
- mechanism relationships
- evidence relationships
- safety relationships

### 4.2 Intervention Product

A real-world product or preparation.

Examples:

- Brand A Ashwagandha 600 mg
- tincture containing three herbs
- tea blend
- standardized curcumin extract with piperine

Fields:

- `product_id`
- brand
- product name
- serving definition
- lot/batch if known
- ingredient list
- standardized constituents
- formulation type
- extraction ratio if known
- excipients
- barcode/UPC if captured
- source of identity
- product verification status

Products may be multi-ingredient.

### 4.3 Product Ingredient

Joins a product to one or more intervention concepts.

Fields:

- `product_ingredient_id`
- `product_id`
- `intervention_concept_id`
- amount per serving
- unit
- standardization value
- uncertainty
- provenance

### 4.4 Intervention Plan

What the system/user/clinician intends to do.

Fields:

- `intervention_plan_id`
- Case
- objectives
- rationale
- intended intervention/product
- intended dose
- intended frequency
- intended timing
- intended duration
- monitoring targets
- safety constraints
- stop conditions
- author/source
- evidence version
- status

### 4.5 Exposure Event

What actually occurred.

This is the most important new primitive.

Fields:

- `exposure_event_id`
- Case
- person
- intervention concept and/or product
- timestamp started
- timestamp ended where applicable
- dose amount
- dose unit
- serving quantity
- route
- formulation
- with food / fasting / meal relationship
- adherence source
- confidence
- provenance
- user-entered vs imported vs inferred
- timezone
- correction lineage
- optional notes

An exposure event must never be fabricated from a plan. If a person was scheduled to take 500 mg and does not confirm the dose, the system records the plan but not a confirmed exposure.

### 4.6 Exposure Interval

Some interventions are better modeled as intervals rather than instantaneous doses.

Examples:

- fasting period;
- continuous glucose sensor use;
- dietary pattern;
- exercise session;
- topical preparation;
- infusion;
- sleep intervention;
- continuous wearable device.

### 4.7 Regimen State

A derived snapshot of exposures active or biologically relevant during a time window.

Examples:

- morning regimen;
- current daily stack;
- experiment phase regimen;
- last 24-hour active exposure set.

Regimen State is derived. It does not replace atomic exposure events.

---

## 5. Daily tracking: how the user tells HerbaGraph what they took

The UX must make adherence capture easy enough to use daily.

Support multiple entry paths.

### 5.1 Planned regimen checklist

HerbaGraph can show the person's expected regimen for the day.

Example:

- Ashwagandha — planned 08:00
- Magnesium — planned 21:00
- Berberine — planned with lunch

The user can tap:

- Taken
- Skipped
- Changed dose
- Took later
- Stopped
- Side effect

### 5.2 One-tap batch confirmation

If a user takes a morning stack together:

> “Taken as planned”

HerbaGraph creates separate atomic exposure events for every ingredient/product while linking them to a common `intake_session_id`.

### 5.3 Voice capture

Example:

> “I took my berberine and magnesium with lunch around 1:15, but only half my normal berberine dose.”

The LLM may parse the statement into proposed exposure events. Deterministic validation must verify product identity, units, dose plausibility, duplicates, and ambiguities before persistence.

### 5.4 Barcode / product scan

Scanning should resolve product identity, ingredient list, serving size, and formulation when trusted data is available.

### 5.5 Photo capture

A user can photograph a supplement label. Extraction remains provisional until sufficiently verified.

### 5.6 Smart reminders

The system may remind the user to confirm an expected exposure, but absence of confirmation remains unknown rather than automatically “missed.”

### 5.7 Passive inference boundaries

HerbaGraph may infer likely adherence from connected pill dispensers or supported devices only if the source semantics justify it. “Container opened” is not equivalent to “dose swallowed.”

---

## 6. Intake sessions

When multiple interventions are taken together, create an `intake_session`.

Fields:

- `intake_session_id`
- Case
- timestamp
- meal context
- fasting context
- free-text note
- source

The session contains multiple exposure events.

This allows HerbaGraph to reason about:

- simultaneous intake;
- absorption competition;
- shared meal context;
- acute combination effects;
- user routines.

Example:

**08:05 Intake Session**

- Ashwagandha 300 mg
- Rhodiola 200 mg
- Magnesium glycinate 200 mg elemental-equivalent
- Coffee 12 oz

The combination may matter more than any single exposure.

---

## 7. Multiple-herb problem: the Regimen Graph

Polyherbal use requires explicit modeling.

For every active pair or group of interventions, HerbaGraph should evaluate multiple relationship dimensions.

### 7.1 Relationship classes

#### Complementary

Different mechanisms support the same objective without known material conflict.

#### Potentially synergistic

Evidence suggests combined effect may exceed simple additive effect.

Use this label conservatively and require evidence provenance.

#### Redundant

Two interventions substantially overlap in mechanism, endpoint, or constituent exposure without clear added value.

Redundancy is not automatically harmful, but it may add cost, complexity, side-effect burden, or attribution difficulty.

#### Antagonistic

One intervention may counteract the biological effect of another.

#### Goal-conflicting

An intervention may help one objective while worsening another objective.

This is essential.

Example pattern:

- intervention A supports alertness/performance;
- intervention A may worsen sleep;
- sleep improvement is also a stated objective.

The system should surface the tradeoff rather than merely score the intervention as “good.”

#### Safety interaction

Combination creates clinically meaningful risk, such as additive anticoagulant, sedative, glycemic, blood-pressure, serotonergic, hepatotoxic, or other supported effects.

#### Absorption interaction

Timing may change absorption or bioavailability.

#### Pharmacokinetic interaction

One intervention may alter metabolism or transport of another compound.

#### Unknown interaction

No adequate evidence.

Unknown must remain a first-class state.

### 7.2 Relationship object

Store interaction claims as evidence-backed graph objects.

Fields:

- intervention A
- intervention B
- relationship type
- target/pathway/end point
- direction
- magnitude if supported
- population/context
- dose context
- timing context
- evidence confidence
- source provenance
- known limitations
- review status

Never allow an LLM to invent a pairwise interaction edge without evidence or an explicitly marked hypothesis state.

---

## 8. Objective Graph

A person may have multiple objectives.

Examples:

- improve glucose stability;
- improve sleep continuity;
- reduce GI symptoms;
- improve daytime energy;
- support blood pressure;
- reduce inflammatory burden;
- avoid sedation;
- preserve exercise performance.

Create an `objective` entity.

Fields:

- `objective_id`
- Case
- user-stated objective
- normalized objective concept
- priority
- target observations
- unacceptable tradeoffs
- time horizon
- status

Each intervention can then have a directed relationship to one or more objectives.

Example:

`rhodiola -> daytime_energy -> SUPPORTS`

`rhodiola -> sleep_onset -> MAY_CONFLICT` when timing or individual response supports that concern.

This prevents HerbaGraph from optimizing one biomarker while degrading the person's broader goals.

---

## 9. Regimen scoring must be multidimensional

Do not create a single opaque “stack score.”

Instead produce a transparent regimen assessment with dimensions such as:

- objective coverage;
- evidence support;
- mechanistic complementarity;
- redundancy burden;
- safety interaction burden;
- goal conflicts;
- attribution complexity;
- adherence complexity;
- monitoring observability;
- cost/burden if relevant.

Example user-facing output:

**Current regimen**

Objective alignment: Strong  
Safety conflicts: 1 requires review  
Redundancy: Moderate  
Attribution quality: Poor  
Monitoring coverage: Good

Then explain exactly why.

---

## 10. Attribution complexity

If a person starts five herbs on the same day and improves three days later, HerbaGraph should not claim to know which herb caused the improvement.

Create an `attribution_quality` state.

Suggested levels:

- **High interpretability** — one material change, stable background, adequate baseline.
- **Moderate interpretability** — limited co-changes or known confounders.
- **Low interpretability** — several simultaneous changes.
- **Uninterpretable** — major uncontrolled changes or insufficient baseline/data.

The system should proactively warn:

> Starting four new interventions simultaneously will make it difficult to determine which one changes your outcomes.

The user may still choose to proceed.

HerbaGraph records the decision and interprets later evidence accordingly.

---

## 11. Experiment design

HerbaGraph should support structured N-of-1 experimentation without overclaiming causal certainty.

### 11.1 Experiment entity

Fields:

- `experiment_id`
- Case
- objective
- intervention(s)
- hypothesis
- primary response markers
- secondary response markers
- safety markers
- planned phases
- start/end dates
- randomization status
- blinding status
- adherence requirements
- confounder controls
- analysis plan version
- status

### 11.2 Experiment phases

Supported phase types:

- baseline/run-in;
- intervention;
- washout;
- rechallenge;
- comparator;
- placebo where appropriate and ethically supported;
- observation-only.

### 11.3 Single-variable-first default

When safe and appropriate, the product should encourage changing one major intervention at a time for attribution quality.

This is guidance, not a mandatory clinical instruction.

### 11.4 Combination experiments

Some interventions are intended as combinations.

The system must support:

- A alone;
- B alone;
- A+B;
- baseline;
- washout.

This permits later estimation of complementarity or antagonism.

---

## 12. Continuous observation model

Wearables are observation sources, not truth sources.

### 12.1 Initial supported streams

Potential early integrations:

- resting heart rate;
- HRV;
- sleep duration;
- sleep fragmentation;
- respiratory rate;
- temperature;
- SpO2;
- steps;
- exercise/activity;
- continuous glucose;
- meal timestamps;
- weight;
- user-reported symptoms;
- mood/stress scores.

### 12.2 Future biosensor streams

Architect for future support without depending on it now:

- cortisol;
- lactate;
- electrolytes;
- sweat glucose;
- interstitial glucose;
- selected inflammatory mediators;
- selected metabolites;
- other validated biochemical sensors.

### 12.3 Observation entity

Fields:

- `observation_id`
- Case
- metric concept
- source device/system
- timestamp
- value
- unit
- sampling interval
- quality flag
- device metadata
- provenance
- ingestion version
- correction/supersession state

Do not silently merge observations from devices with materially different semantics.

---

## 13. Derived features

Raw data should remain preserved.

Derived features may include:

- daily resting HR;
- nightly HRV summary;
- sleep efficiency;
- sleep fragmentation;
- glucose mean;
- glucose standard deviation;
- coefficient of variation;
- postprandial AUC;
- nocturnal temperature deviation;
- activity load;
- symptom burden score.

Derived metrics must record:

- derivation algorithm;
- version;
- input observations;
- time window;
- missingness;
- quality.

---

## 14. Personal baseline

HerbaGraph should prioritize within-person change rather than population-normal comparison when evaluating intervention response.

Create versioned baselines.

A baseline has:

- metric;
- time period;
- inclusion/exclusion rules;
- number of observations;
- variability estimate;
- device/source;
- context;
- confidence.

Baselines may need stratification by:

- weekday/weekend;
- meal type;
- menstrual/cycle context where user chooses to track;
- activity day;
- sleep duration;
- time of day;
- medication state.

---

## 15. Response Engine

The Response Engine compares observed trajectories against baseline and experiment context.

It should answer:

- Did a monitored metric change?
- When did change begin?
- Was change sustained?
- Was change larger than expected personal variability?
- Did multiple related metrics move coherently?
- Was there a dose-response pattern?
- Was the pattern reproduced on rechallenge?
- Did the pattern disappear on washout?
- Were major confounders present?

The engine outputs a **response finding**, not a causal verdict.

Example:

> Nocturnal HRV increased relative to the prior 14-day baseline during the intervention phase. The association is temporally consistent but attribution is limited because sleep duration also increased during the same period.

---

## 16. Response signatures

A natural-product intervention may generate a multivariate signature rather than one endpoint.

Represent a response vector conceptually as:

`R(t) = [glucose, HRV, resting_HR, sleep, symptom_score, temperature, ...]`

The system may compare:

- predicted mechanism signature;
- observed signature;
- expected response timing;
- contradictions.

This creates a research-grade feedback loop between the knowledge graph and real-world observation.

---

## 17. Confounder model

Confounders must be first-class entities.

Examples:

- sleep duration;
- illness;
- alcohol;
- caffeine;
- major dietary change;
- fasting;
- exercise;
- travel;
- stress;
- medication change;
- menstrual/cycle state if voluntarily tracked;
- sensor failure;
- missing adherence;
- acute infection;
- unusual meal pattern.

Store confounder events with timestamps and uncertainty.

The system may reduce attribution confidence when confounding exposure overlaps the response window.

---

## 18. Temporal pharmacology and botanical kinetics

Different interventions have different plausible response windows.

The graph should eventually represent:

- onset range;
- expected duration;
- accumulation;
- half-life where scientifically meaningful;
- metabolite persistence;
- acute vs chronic mechanism;
- washout assumptions.

Do not use a universal “four-hour herb window.”

If evidence is unavailable, mark the temporal model as uncertain.

---

## 19. Goal-conflict engine

The user specifically needs protection against interventions that help one goal while undermining another.

Create objective-level edges:

- SUPPORTS
- MAY_SUPPORT
- NEUTRAL/UNKNOWN
- MAY_CONFLICT
- CONFLICTS
- SAFETY_BLOCK

Example:

An intervention may:

- improve daytime alertness;
- worsen sleep if taken late;
- therefore create a timing-dependent goal conflict.

Goal conflict evaluation should consider:

- objective priority;
- timing;
- dose;
- individual observed response;
- evidence quality;
- safety significance.

The user-facing system should explain tradeoffs rather than hiding them inside a recommendation rank.

---

## 20. Synergy and complementarity

HerbaGraph should distinguish:

- shared objective;
- different mechanism;
- mechanistic synergy;
- clinical synergy.

Mechanistic plausibility alone is not sufficient to claim clinical synergy.

An interaction may be stored as:

`COMPLEMENTARY_MECHANISMS`

without being promoted to:

`CLINICALLY_SYNERGISTIC`

unless stronger evidence supports that claim.

---

## 21. Redundancy control

Many supplement stacks become unnecessarily complex.

HerbaGraph should detect:

- duplicate ingredients across products;
- same constituent under different botanical names;
- overlapping high-dose nutrients;
- multiple interventions targeting the same pathway;
- redundant sedatives/stimulants;
- repeated standardized extracts.

Example:

A user may take a multivitamin, magnesium complex, electrolyte powder, and separate magnesium supplement. The system should calculate total daily exposure where possible.

Create `daily_aggregate_exposure` for nutrients/constituents where summation is scientifically valid.

---

## 22. Product mixtures and hidden ingredients

Multi-ingredient products create attribution problems.

The system must preserve both levels:

- product exposure;
- ingredient exposures derived from the product.

If ingredient quantities are proprietary or unknown, the derived exposure remains uncertain.

Never invent amounts.

---

## 23. Medication and non-herbal interactions

Even if HerbaGraph remains botanically focused, real-world safety requires representing medication and relevant non-botanical exposures.

Initial implementation can treat these as interaction/safety context rather than full prescribing logic.

Important rule:

> Absence of a known interaction edge must never be presented as proof that a combination is safe.

---

## 24. Safety engine integration

Before an intervention plan is presented, and whenever the regimen changes, the Safety Engine should evaluate the active regimen.

Potential classes include:

- additive bleeding risk;
- additive sedation;
- additive stimulation;
- glycemic lowering;
- blood-pressure lowering;
- serotonergic concerns;
- hepatotoxicity concerns;
- renal concerns;
- pregnancy/lactation constraints;
- allergy;
- surgery timing;
- medication interactions;
- dose-limit concerns where supported.

Safety edges require evidence and provenance.

Founder approval remains required for material changes to medical safety behavior.

---

## 25. Data lineage and epistemic states

Every exposure-related fact must distinguish:

- planned;
- user-reported;
- device-imported;
- inferred;
- verified;
- corrected;
- superseded;
- unknown.

Do not collapse these states.

Example:

“Scheduled at 8 AM” is not “taken at 8 AM.”

“Bottle opened at 8 AM” is not “swallowed at 8 AM.”

“User said they usually take it in the morning” is not a confirmed historical exposure event for each day.

---

## 26. Correction and replay invariants

All existing Case invariants remain.

New hostile-path requirements:

- correcting a dose must supersede rather than mutate history invisibly;
- retrying an intake confirmation must not duplicate exposure events;
- changing a product label must not rewrite prior batches unless explicitly linked;
- a plan change must not rewrite past exposures;
- an inferred exposure must never overwrite a user-confirmed exposure;
- regimen reconstruction from atomic events must be deterministic;
- imported wearable duplicates must be idempotently deduplicated;
- changing timezone representation must not change physiological ordering.

---

## 27. Attribution hierarchy

HerbaGraph should use a conservative hierarchy.

### Level 0 — Observation only

Metric changed.

### Level 1 — Temporal association

Metric changed after intervention exposure.

### Level 2 — Pattern consistency

Timing and mechanism are consistent with the intervention hypothesis.

### Level 3 — Reproducible within-person association

Pattern recurs on rechallenge or controlled repeated exposure.

### Level 4 — Comparative N-of-1 evidence

Structured phases support a stronger within-person association.

Even at high levels, do not present a clinical diagnosis or universal causal truth.

---

## 28. Example: three-herb regimen

User objective priorities:

1. Improve sleep continuity.
2. Improve daytime energy.
3. Reduce glucose variability.

Current exposures:

- Ashwagandha nightly.
- Rhodiola in the morning.
- Berberine with lunch and dinner.

HerbaGraph should not simply evaluate each herb independently.

It should produce:

### Objective graph

Ashwagandha → sleep continuity: potential support.  
Rhodiola → daytime energy: potential support.  
Berberine → glucose variability: potential support.

### Interaction graph

Ashwagandha + Rhodiola: evidence/context-dependent; do not assume synergy.  
Rhodiola late in day → sleep objective: possible timing conflict.  
Berberine + glucose-lowering medication if present: safety interaction review.

### Attribution graph

If all three started the same day, attribution quality is low.

### Monitoring plan

- nightly HRV;
- sleep fragmentation;
- daytime energy score;
- CGM variability;
- meal-linked glucose response;
- adverse symptoms.

The product can then recommend improving experiment interpretability, such as stabilizing the regimen or testing one change at a time where appropriate.

---

## 29. Example: complementary vs conflicting interventions

Suppose the user wants lower stress and better daytime performance.

Intervention A reduces subjective arousal but produces daytime sedation.

Intervention B increases alertness but elevates nighttime heart rate when taken late.

The system should not rank A and B separately and conclude both are “good.”

It should model:

- A supports stress objective;
- A conflicts with daytime performance objective;
- B supports daytime performance;
- B may conflict with sleep/recovery depending on timing;
- combination may produce an unstable push-pull regimen.

This is precisely why HerbaGraph needs an objective-aware regimen model.

---

## 30. Wearable ingestion architecture

Implement an adapter model.

`WearableAdapter`

Responsibilities:

- authentication/token handling outside PHI-unsafe logs;
- source-specific field normalization;
- timestamp normalization;
- unit normalization;
- quality flags;
- provenance;
- retry/idempotency;
- source deletion/revocation behavior.

Potential adapters:

- Apple Health/HealthKit bridge;
- Oura;
- Garmin;
- Whoop;
- Fitbit;
- Dexcom or supported CGM integrations;
- manual CSV/FHIR where appropriate.

Do not hard-wire the core response engine to a single vendor.

---

## 31. Research architecture and NIH relevance

The platform should be capable of supporting natural-product studies where investigators ask whether a standardized intervention produces a measurable biological signature.

Research-ready capabilities should include:

- protocol-defined intervention identity;
- lot/formulation capture;
- adherence capture;
- baseline period;
- intervention periods;
- washout/rechallenge;
- predefined outcomes;
- continuous wearable measures;
- periodic laboratory anchors;
- confounder capture;
- versioned analysis plan;
- audit/provenance;
- exportable de-identified research dataset;
- consent and secondary-use governance.

Future research objective:

> Continuous phenotyping of biological responses to natural-product interventions.

---

## 32. Learning Network

With valid consent and governance, HerbaGraph may eventually learn population-level patterns such as:

- responder phenotypes;
- non-responder phenotypes;
- dose-response patterns;
- common goal conflicts;
- combination patterns;
- adverse response signatures;
- measurement strategies with highest information value;
- intervention-response timing distributions.

These outputs remain hypothesis-generating unless appropriately validated.

The learning system must not silently promote aggregate correlations into user-specific causal truth.

---

## 33. Proposed data model additions

Indicative tables/entities:

- `intervention_concepts`
- `intervention_products`
- `product_ingredients`
- `intervention_plans`
- `exposure_events`
- `exposure_intervals`
- `intake_sessions`
- `objectives`
- `objective_intervention_edges`
- `intervention_interaction_claims`
- `regimen_snapshots`
- `experiments`
- `experiment_phases`
- `observation_streams`
- `observations`
- `derived_features`
- `personal_baselines`
- `confounder_events`
- `response_findings`
- `attribution_assessments`
- `response_signatures`
- `monitoring_plans`
- `safety_events`

Use repository naming conventions and inspect current models before migration design.

---

## 34. API surface proposal

Illustrative, not final.

### Exposure

- `POST /v1/cases/{case_id}/exposures`
- `GET /v1/cases/{case_id}/exposures`
- `POST /v1/cases/{case_id}/intake-sessions`
- `POST /v1/cases/{case_id}/exposures/{id}/correct`

### Regimen

- `GET /v1/cases/{case_id}/regimen/current`
- `GET /v1/cases/{case_id}/regimen/interactions`

### Objectives

- `POST /v1/cases/{case_id}/objectives`
- `GET /v1/cases/{case_id}/objectives`

### Monitoring

- `POST /v1/cases/{case_id}/observations`
- `GET /v1/cases/{case_id}/monitoring/timeline`

### Experiments

- `POST /v1/cases/{case_id}/experiments`
- `GET /v1/cases/{case_id}/experiments/{id}`
- `POST /v1/cases/{case_id}/experiments/{id}/phases`

### Analysis

- `GET /v1/cases/{case_id}/responses`
- `GET /v1/cases/{case_id}/attribution`

All write endpoints require owner scoping, idempotency, audit, and provenance conventions consistent with the Case architecture.

---

## 35. UI proposal

### Today tab

Simple surface:

- planned interventions;
- one-tap taken/skipped;
- current monitoring status;
- warnings;
- symptom check-in.

### Regimen tab

Shows:

- everything currently being taken;
- total ingredient exposure;
- complementary relationships;
- redundancies;
- interactions;
- goal conflicts;
- attribution complexity.

### Timeline tab

Overlay:

- exposure events;
- meals;
- exercise;
- sleep;
- symptoms;
- wearable metrics;
- labs;
- experiment phases.

### Experiment tab

Shows:

- baseline;
- intervention;
- washout;
- monitoring targets;
- adherence;
- confounders;
- response summary.

### Response tab

Shows:

- what changed;
- magnitude;
- onset;
- persistence;
- conflicting measures;
- attribution quality;
- evidence limitations.

---

## 36. UX principle: low-friction capture, high-rigor interpretation

The user should not be forced to fill out a research CRF every day.

Daily interaction should often be one tap.

Complexity belongs underneath:

> “Taken as planned.”

should create rich structured events based on the active plan.

If the user changes something, capture only the difference.

---

## 37. MVP sequencing

Do not delay the current HerbaGraph MVP to build hardware.

### Phase A — Exposure Ledger

Build:

- intervention products;
- plan vs actual exposure distinction;
- intake sessions;
- daily adherence UI;
- correction/idempotency.

### Phase B — Regimen Intelligence

Build:

- active regimen reconstruction;
- duplicate ingredient detection;
- evidence-backed interaction edges;
- objective graph;
- goal-conflict UI;
- attribution complexity.

### Phase C — Wearable integration

Start with a limited set of high-value streams.

Suggested first targets:

- sleep;
- resting HR;
- HRV;
- activity;
- CGM when connected.

### Phase D — Experiment Engine

Build baseline/intervention/washout/rechallenge workflows.

### Phase E — Response Engine

Add versioned derived features and response findings.

### Phase F — Research mode

Add protocol, study export, consent, stronger audit, investigator controls.

### Phase G — Experimental biosensors

Partner with academic/industry sensor groups rather than designing first-party hardware prematurely.

---

## 38. MVP acceptance criteria for Exposure Ledger

1. User can define a planned daily intervention.
2. User can confirm an exposure in one action.
3. Plan and actual exposure are stored separately.
4. Multi-product intake creates separate atomic events linked by session.
5. Multi-ingredient products preserve ingredient decomposition.
6. Repeated submission is idempotent.
7. Corrections preserve history.
8. Skipped/unknown/taken are not conflated.
9. Current regimen can be deterministically reconstructed.
10. No real patient data appears in fixtures/tests.

---

## 39. MVP acceptance criteria for Regimen Intelligence

1. Current regimen lists all active interventions.
2. Duplicate ingredient exposure can be detected.
3. Evidence-backed pairwise interaction claims preserve provenance.
4. Unknown interaction state remains explicit.
5. Objective conflicts are represented separately from safety interactions.
6. User can see why a conflict was surfaced.
7. System never infers synergy from pathway overlap alone.
8. Starting several interventions simultaneously lowers attribution quality.
9. Safety Engine continues to govern high-risk combinations.
10. Commerce cannot affect regimen ranking or interaction logic.

---

## 40. MVP acceptance criteria for continuous monitoring

1. Observations retain source and timestamp provenance.
2. Raw data is preserved separately from derived metrics.
3. Duplicate imports do not duplicate observations.
4. Missing data is visible.
5. Device differences are not silently blended.
6. Personal baselines are versioned.
7. Response findings state association, not causality.
8. Confounders reduce attribution confidence appropriately.
9. Wearable data cannot close an investigation branch merely because a metric normalized.
10. User-facing language avoids diagnostic certainty.

---

## 41. Hostile-path tests

Required examples:

### Exposure

- planned dose without confirmation does not become actual exposure;
- duplicate “taken” callback does not create two exposure rows;
- correction from 500 mg to 250 mg leaves original superseded;
- user-entered confirmed dose outranks passive inferred adherence;
- proprietary blend does not invent ingredient quantities.

### Polyherbal

- five herbs started simultaneously result in low attribution quality;
- duplicate magnesium across products is detected;
- unknown herb-herb pair does not render “safe”;
- mechanistic overlap does not render “synergy” without evidence;
- intervention supporting goal A but worsening goal B is surfaced as a goal conflict.

### Monitoring

- HRV improvement plus major simultaneous sleep improvement is not attributed solely to herb;
- missing wearable data is not treated as normal;
- device timezone shift does not reorder exposures;
- sensor replacement does not silently merge baselines across incompatible devices;
- washout with no adherence confirmation cannot be assumed complete.

### Case integrity

- replay does not duplicate exposure, response, or experiment records;
- corrections survive rebuild;
- inactive/superseded exposure does not reappear in active regimen;
- unrelated wearable metric does not close an Investigation Map branch.

---

## 42. Research questions this architecture enables

HerbaGraph can eventually study:

- Which natural products generate reproducible within-person physiological response signatures?
- Which baseline phenotypes predict response?
- What combinations show complementary versus antagonistic patterns?
- Which response metrics are most sensitive to each intervention class?
- What is the typical onset and decay time of observed response signatures?
- Which user behaviors most strongly confound supplement self-experimentation?
- Does structured single-variable experimentation improve attribution quality compared with uncontrolled stack changes?
- Can predicted graph mechanisms be prospectively matched against observed response vectors?

---

## 43. Strategic moat update

The moat expands from:

**structured evidence + explainable discovery + longitudinal investigation**

into:

**structured evidence + explainable discovery + longitudinal investigation + exposure truth + regimen interaction graph + continuous response phenotyping + governed attribution + responder learning network**.

The valuable dataset is not merely:

> Person X took herb Y.

It is:

> Person X, with baseline state B and objectives O, took standardized exposure E at time T within regimen R, under confounders C, producing observation trajectory Z with attribution quality Q and evidence provenance P.

That structure is substantially more defensible and more useful for research.

---

## 44. Founder decisions encoded by this specification

1. HerbaGraph should pursue a future closed-loop intervention-response architecture.
2. Existing consumer wearables and CGM should precede custom hardware.
3. Hardware should remain replaceable behind a vendor-neutral observation layer.
4. Actual exposure must be separated from planned intervention.
5. Daily tracking must support one-tap confirmation and multi-intervention intake sessions.
6. Multiple herbs must be evaluated as a regimen, not only independently.
7. Complementarity, synergy, redundancy, antagonism, safety interaction, and goal conflict are separate relationship types.
8. User objectives must be explicit graph entities.
9. Goal conflict must be evaluated independently from safety.
10. Simultaneous intervention changes must reduce attribution confidence.
11. Unknown interactions must never be presented as safe interactions.
12. Mechanistic plausibility must not be mislabeled as demonstrated clinical synergy.
13. Response findings must distinguish observation, temporal association, reproducibility, and stronger N-of-1 evidence.
14. Continuous data must preserve raw provenance and versioned derived features.
15. The platform should support NIH/NCCIH-style natural-product biological-signature research without making the current MVP dependent on new sensor hardware.

---

## 45. Immediate implementation work for Grok

Grok should **not implement the entire specification in one PR**.

The next implementation tranche should be the Exposure Ledger foundation only.

Recommended first issue/PR scope:

1. Inspect current Case, intervention, monitoring, timeline, and safety models.
2. Propose minimal schema additions for:
   - intervention plan;
   - intervention product;
   - exposure event;
   - intake session.
3. Preserve current intervention behavior behind compatibility adapters if necessary.
4. Add deterministic idempotency keys for exposure confirmation.
5. Add correction/supersession behavior.
6. Add APIs for recording and listing exposure events.
7. Add unit tests and hostile-path tests.
8. Do not yet add wearable vendor integrations.
9. Do not yet add probabilistic causal attribution.
10. Do not rewrite the Safety Engine.
11. Do not promote mechanistic interactions to user-facing synergy without evidence.
12. Open implementation PR to `integration/agent` with migration and rollback notes.

---

## 46. Architectural boundary

This document is a roadmap and system contract, not blanket authorization to modify production clinical safety behavior, PHI handling, consent, or production infrastructure.

Before implementing each phase, Grok must inspect the current repository state and preserve the repository's existing evidence, safety, Case integrity, migration, and review invariants.

The central principle is:

> **HerbaGraph should know what was planned, what was actually taken, what else was active at the same time, what the person was trying to accomplish, what changed afterward, and how uncertain the attribution remains.**

That is the foundation for a trustworthy closed-loop natural-product reasoning system.
