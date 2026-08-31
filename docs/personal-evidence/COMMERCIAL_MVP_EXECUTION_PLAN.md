# HerbaGraph Commercial MVP Execution Plan

**Architecture parent:** #65 / PR #66  
**Target implementation lane:** `integration/agent`  
**Purpose:** Convert HerbaGraph's existing Discovery, knowledge-graph, laboratory, evidence, and safety capabilities into a commercially testable product without rebuilding working intelligence.  
**Primary commercial gate:** A supported user with an expensive unresolved health question should receive enough unique, explainable value from HerbaGraph that they would voluntarily return, share the output, or pay to preserve and extend the Case.

---

## 1. Founder decision encoded by this plan

HerbaGraph will not respond to commercial pressure by becoming a generic supplement recommender, wellness chatbot, or feature-heavy dashboard.

The commercial MVP will concentrate existing and new capabilities into five user-visible value pillars:

1. **Health Investigation Audit** — identify what is known, what remains unresolved, what prior evidence actually addressed, what may have been overinterpreted, and where additional spending may be low value.
2. **Best-in-class Ask / Discovery** — ask the smallest number of high-value questions needed to change the Case, not merely continue conversation.
3. **Regimen Truth + Regimen Review** — know exactly what the user plans to take, what they actually took, what remains identity-ambiguous, what overlaps, and what makes attribution difficult.
4. **Unified Next Best Action** — rank the next action by decision value, coverage gain, safety, redundancy, burden, cost, reversibility, and interpretability rather than novelty or commerce.
5. **Living Evidence Passport** — preserve what was tried, why, what happened, what can reasonably be inferred, and what remains uncertain.

Signals, formal N-of-1 Experiments, Attribution, wearable integrations, and research workflows remain strategically important, but they follow the commercial proof point unless required to preserve architecture compatibility.

---

## 2. Reuse-first rule

Before adding a new subsystem, the Implementer must inspect whether the needed capability already exists in:

- `app/discovery/`
- `app/coverage/`
- `app/pipeline/`
- `app/knowledge_graph/`
- `app/evidence_confidence/`
- `app/safety_engine/`
- existing Case, lab, report, authorization, audit, consent, and telemetry code.

The following existing capabilities are **not to be rebuilt** unless a reviewed defect requires replacement:

- longitudinal Case truth and Case versioning;
- Discovery conversation orchestration;
- evidence coverage semantics;
- branch lifecycle rules;
- append-only correction/supersession;
- scientific-output validation;
- literature claim provenance;
- safety escalation;
- biomarker normalization;
- biological-system/pathway reasoning;
- laboratory ingestion and reporting;
- evidence retrieval;
- knowledge-graph catalogs and entity registry;
- food/nutrient catalog infrastructure;
- composition/form/assay identity semantics;
- the existing next-best-investigation ranker mathematics.

If a new package exposes these capabilities to Personal Evidence, it should initially use adapters or stable service contracts rather than duplicate the underlying logic.

---

## 3. Current repository capabilities that form the commercial foundation

### 3.1 Discovery and Case

Existing Discovery already provides or partially provides:

- Case creation/resumption;
- normalized findings;
- contradiction detection;
- adaptive next-question selection;
- safety state;
- investigation branches and gaps;
- workup inventory;
- evidence relationships;
- coverage-aware lifecycle rules;
- investigation map;
- Case-version coherence;
- corrections and supersession;
- next-best investigation ranking;
- literature claim cards;
- PHI-safe telemetry;
- return-visit memory.

### 3.2 Identity and evidence applicability

`app/discovery/composition.py` and its graph already establish the important abstraction that a biological concept is not interchangeable with a form, preparation, product batch, exposure, assay, or claim.

The commercial MVP must preserve and extend these semantics rather than flatten them.

Examples that must remain true:

- unknown magnesium form remains unknown;
- compound mass is not silently treated as elemental magnesium;
- magnesium oxide evidence does not automatically transfer to magnesium glycinate;
- a parent nutrient does not automatically lend all claims to a child form;
- serum B12, MMA, holotranscobalamin, and homocysteine are measurements with distinct coverage semantics, not interchangeable statements of biological truth;
- product-batch findings do not automatically transfer to every product with the same marketing label;
- ontology/example evidence cannot enter an unrelated Case.

### 3.3 Existing next-best-action logic

`app/discovery/ranker.py` already scores candidates using information value, coverage gain, safety, redundancy, cost, and burden. This is the starting point for a future Case-wide decision engine. It should not be replaced with an LLM ranking prompt.

### 3.4 Existing frontend

The current static workspace and Ask frontend remain the Phase-I shell.

Do not introduce React, Next.js, Vue, a second SPA, or another persistence layer for this MVP.

`frontend/js/workspace-app.js` is already too large to remain the home of every new Personal Evidence feature. New commercial modules should be extracted behind the existing shell.

---

## 4. Target product architecture

```text
                         HERBAGRAPH

                 Shared Reasoning Contracts
        ┌─────────────────────────────────────────┐
        │ Case truth                              │
        │ Identity / composition                  │
        │ Measurement / coverage                  │
        │ Evidence / provenance                   │
        │ Scientific governance                   │
        │ Safety                                  │
        │ Decision ranking                        │
        └──────────────────┬──────────────────────┘
                           │
        ┌──────────────────┼───────────────────────┐
        │                  │                       │
        ▼                  ▼                       ▼
   Discovery / Ask   Commercial Audit       Personal Evidence
        │                  │                       │
        │                  │             Regimen / Exposure
        │                  │                       │
        └──────────────────┴──────────► Updated Case

       Later: Signals -> Experiments -> Attribution -> Passport
```

The Shared Reasoning layer is initially a contract boundary, not a mandatory physical relocation of all files.

---

## 5. Commercial MVP success definition

A commercially testable MVP is complete when a supported user can:

1. start or resume a Case from natural language;
2. answer high-value Discovery questions without unnecessary repetition;
3. upload supported labs and prior records;
4. see a coherent **My Case** view;
5. receive a **Health Investigation Audit** containing evidence-backed and provenance-linked findings;
6. see what prior testing did and did not evaluate;
7. see unresolved evidence gaps and contradictions;
8. identify at least one high-value uncertainty, misunderstanding, or waste-risk when one is actually supported by the Case;
9. add a current regimen without inventing unknown product/form/dose details;
10. record actual intake separately from planned regimen;
11. receive a bounded Regimen Review using explainable issue types;
12. see one ranked Next Best Action with a transparent rationale;
13. correct information without destroying history;
14. reload/return without losing canonical state;
15. share or export a concise Case summary suitable for a clinician or trusted reviewer;
16. encounter partial, unknown, unsupported, stale, and failed states without plausible-looking false success.

Commercial UAT should then measure whether users voluntarily share, return, or pay. Engineering completion does not prove product-market fit.

---

# PART I — BACKEND EXECUTION

## 6. Packet A — Shared Reasoning Contracts

### Objective

Allow Discovery, Health Audit, Regimen, and future Personal Evidence modules to use existing intelligence through stable contracts without copying Discovery internals.

### Proposed package

```text
app/intelligence/
    __init__.py
    identity.py
    measurement.py
    evidence.py
    decision.py
    scientific_governance.py
    safety.py
```

These files may initially delegate to existing modules. Avoid high-risk code movement in the first packet.

### Required service contracts

#### Identity service

```text
resolve_identity(candidate) -> IdentityResolution
compare_identity(source, target) -> IdentityApplicability
compute_amount_semantics(identity, amount, unit) -> AmountResolution
```

Required states:

- verified
- user_confirmed
- candidate
- unresolved
- superseded

Unknown remains an allowed output.

#### Measurement service

```text
evaluate_coverage(measurement, target_question) -> CoverageAssessment
```

Coverage classes must remain semantically separate from result interpretation.

#### Evidence service

```text
get_claim_evidence(claim, case_context) -> EvidenceBundle
check_applicability(evidence, target_identity, target_endpoint, context) -> ApplicabilityAssessment
```

#### Decision service

Expose the existing deterministic ranker through a generic candidate contract while preserving existing Discovery behavior.

### Packet A non-goals

- no new medical claims;
- no enterprise public API;
- no broad ontology migration;
- no replacement of existing Discovery imports until compatibility is proven;
- no behavior change to the gold Discovery cases.

---

## 7. Packet B — My Case projection

### Objective

Expose existing Case intelligence as a coherent product surface without creating a second source of truth.

### Backend projection

Create a read-only assembly layer, location chosen after inspection, for example:

```text
app/case_projection/
    assembler.py
    schemas.py
```

or equivalent under the accepted Personal Evidence boundary.

### Response contract

```text
CaseOverview {
    case_id
    case_version
    snapshot_id
    generated_at
    concerns[]
    current_findings[]
    prior_workup[]
    open_branches[]
    evidence_gaps[]
    contradictions[]
    coverage_explanations[]
    next_best_action
    data_completeness
    unresolved_count
    permissions
    feature_flags
}
```

This is a projection only. It may not mutate scientific state.

### Staleness rule

All material sections rendered together must come from the same Case version. Mixed Case versions are a release blocker.

---

## 8. Packet C — Health Investigation Audit

### Objective

Transform existing Case intelligence into a paid-worthy artifact that identifies expensive misunderstandings, unresolved gaps, identity uncertainty, and low-value repetition without diagnosing or inventing problems.

### Canonical audit sections

```text
AuditVersion
├── WhatWeKnow[]
├── WhatTheEvidenceActuallyAddresses[]
├── OpenQuestions[]
├── PotentialMisunderstandings[]
├── IdentityUncertainties[]
├── Contradictions[]
├── PriorWorkupSummary[]
├── RegimenIssues[]                # empty until Regimen packet
├── PotentialLowValueRepeats[]
└── NextBestAction
```

### Audit finding schema

```text
AuditFinding {
    finding_id
    type
    title
    plain_language_explanation
    severity_or_priority          # not disease severity
    source_refs[]
    case_version
    confidence_class
    limitations[]
    allowed_interpretation
    prohibited_interpretation
    next_action_ref?
}
```

### Initial finding types

- `TEST_COVERAGE_MISMATCH`
- `UNVERIFIED_RECALLED_RESULT`
- `OPEN_EVIDENCE_GAP`
- `CONTRADICTION_REQUIRES_CLARIFICATION`
- `IDENTITY_UNRESOLVED`
- `AMOUNT_SEMANTICS_UNRESOLVED`
- `NON_ADDRESSING_EVIDENCE_OVERINTERPRETED`
- `REPEATED_TEST_LOW_INFORMATION_VALUE`
- `INSUFFICIENT_DATA`

Later regimen-specific types are added in Packet E.

### No-finding behavior

If the Case does not support a meaningful audit issue, the system must say so. It must not invent a “wow insight.”

Example:

> “HerbaGraph did not identify a supported mismatch in the records currently available. The largest limitation is missing source documentation for X.”

The commercial gate never overrides scientific truth.

---

## 9. Packet D — Regimen Truth + IntakeSession

### Objective

Answer two questions truthfully:

1. What does this person currently plan/report using?
2. What did this person actually take, when, and with what uncertainty?

### Required entities

#### ProductCapture

Candidate source only. OCR/manual/barcode/import does not equal verified identity.

#### ProductIdentity

Must preserve exact ingredient and decision-relevant dimensions where known:

- parent concept;
- chemical/nutrient identity;
- botanical species;
- plant part;
- preparation/extract;
- form;
- formulation;
- route;
- amount semantics;
- serving basis;
- manufacturer/product/version where available;
- verification status;
- provenance.

#### RegimenVersion

Immutable planned/reported snapshot.

#### RegimenItem

A planned/reported item in the regimen. It is not proof of ingestion.

#### IntakeSession

Groups multiple items taken together as one user action while preserving atomic exposures.

```text
IntakeSession {
    id
    case_id
    occurred_at
    reported_at
    context
    source_command_id
    correction_lineage
}
```

#### ExposureEvent

```text
ExposureEvent {
    id
    case_id
    intake_session_id?
    regimen_item_id?
    product_identity_id
    actual_amount
    unit
    route
    occurred_at
    reported_at
    relation_to_plan
    source
    source_command_id
    provenance
    active
    supersedes_id?
}
```

### Semantic idempotency

The same semantic command replay must return the same result and must not create duplicate exposure rows.

Recommended unique semantic key:

```text
(case_id, source_command_id)
```

for the mutation command, with child exposure identities deterministically tied to the command and included regimen items.

### Intake rules

- `Taken all` creates one IntakeSession and separate ExposureEvents.
- unchecked items are **unconfirmed**, not skipped;
- explicit Skip is a separate reported state;
- no confirmation means unknown;
- planned dose never becomes actual exposure automatically;
- bottle opened does not equal swallowed;
- proprietary blend amounts remain unknown when not disclosed;
- correction is append-only.

---

## 10. Packet E — Regimen Review

### Objective

Turn exact regimen truth into immediate commercial value without becoming an unconstrained recommendation engine.

### Required new objects

```text
UserObjective
ObjectiveConstraint
RegimenAssessment
RegimenIssue
```

### Example UserObjective

```text
improve sleep continuity
reduce GI discomfort
improve daytime energy
support glucose stability
```

### Example ObjectiveConstraint

```text
avoid daytime sedation
avoid worsening constipation
preserve exercise performance
minimize pill burden
```

### RegimenIssue classes

#### Identity

- unknown form;
- ambiguous amount semantics;
- unresolved ingredient;
- missing botanical species/part/preparation when decision-relevant;
- proprietary blend amount unavailable.

#### Redundancy

- exact duplicate ingredient;
- overlapping disclosed constituent;
- overlapping intended objective;
- mechanistic redundancy only when supported and explicitly qualified.

#### Safety

Use existing governed safety/interaction infrastructure where applicable. Unknown does not mean safe.

#### Objective conflict

Only emit when a supported relationship exists between a regimen item and an explicit UserObjective or ObjectiveConstraint.

#### Experimental interpretability

Examples:

- multiple material changes started together;
- dose changed while another intervention started;
- no stable baseline;
- exposure timing unknown;
- poor data completeness.

#### Burden

- excessive intake sessions;
- high logging complexity;
- high unresolved identity burden.

### Do not create one opaque regimen score

Return explainable dimensions and issue cards.

---

## 11. Packet F — Unified Next Best Action

### Objective

Generalize the existing deterministic Discovery ranker rather than replace it.

### Generic candidate contract

```text
DecisionCandidate {
    candidate_id
    type
    objective
    safety
    information_value
    coverage_gain
    redundancy
    cost
    burden
    reversibility
    interpretability_gain
    prerequisites[]
    explanation
    provenance[]
}
```

### Initial candidate types

- `ASK_CLARIFYING_QUESTION`
- `REQUEST_DOCUMENT`
- `UPLOAD_LABS`
- `RESOLVE_IDENTITY`
- `CONFIRM_AMOUNT_SEMANTICS`
- `REVIEW_REGIMEN_ISSUE`
- `RECORD_BASELINE`
- `WAIT_FOR_MORE_DATA`
- `SEEK_PROFESSIONAL_REVIEW`

Formal experiment actions may be added later.

### Scientific ranking rules

- commerce cannot alter rank;
- contraindicated actions are ineligible;
- completed/redundant actions are ineligible;
- non-addressing actions cannot masquerade as information gain;
- safety overrides normal ranking;
- rank must be reconstructable from stored candidate components and ranker version.

---

## 12. Packet G — Declarative Discovery domains

### Objective

Remove long-term enterprise dependence on hard-coded symptom fixtures without breaking existing Discovery gold paths.

### Approach

Do not rewrite the orchestrator. Extract domain-specific discriminators progressively.

Proposed:

```text
app/discovery/domains/
    schema.py
    registry.py
    neurological_sensory.yaml
    upper_abdominal.yaml
```

### Discriminator contract

```yaml
code: distribution
question: "Where do you notice it most?"
purpose: distinguish_pattern_distribution
information_gain: 0.80
required_before: []
safety_class: routine
changes:
  - branch_family_a
  - branch_family_b
```

### Required proof

The existing burning-feet and upper-abdominal gold cases must produce semantically equivalent Case state before and after migration to declarative configuration.

---

# PART II — FRONTEND EXECUTION

## 13. Frontend shell remap

The current frontend should be reorganized around user jobs rather than implementation history.

### Target navigation

```text
HOME
  Home

INVESTIGATE
  Ask
  My Case

MY EVIDENCE
  Today
  Regimen
  Signals
  Experiments
  What I Learned
  Passport

DATA
  Labs
  Documents

ACCOUNT
  Settings
  Consent
```

For commercial MVP, Signals, Experiments, What I Learned, and Passport may appear as intentional disabled/coming-later modules only if product design approves that behavior. Do not fake data or functionality.

### Old top-level destinations

- `Analyze` should be absorbed into the relevant workflow rather than remain a conceptual product.
- `My reports` becomes an output/export concept attached to Case/Passport rather than a primary mental model.
- existing functionality must remain reachable during migration.

---

## 14. Frontend modularization

`workspace-app.js` should retain:

- auth/session bootstrap;
- patient context;
- shell/navigation;
- route dispatch;
- shared error handling;
- shared API wrapper where appropriate.

New modules should be extracted, for example:

```text
frontend/js/modules/
    registry.js

frontend/js/case/
    overview.js
    audit.js

frontend/js/personal-evidence/
    api.js
    state.js
    components.js
    today.js
    regimen.js
    regimen-review.js
```

Do not introduce a new framework solely for modularity.

---

## 15. My Case UX

The page should answer:

- What did I tell HerbaGraph?
- What do we know?
- What remains uncertain?
- What did prior tests actually evaluate?
- What evidence supports or weakens each investigation branch?
- What is contradictory?
- What changed recently?
- What is the next best step and why?

### Required sections

```text
Case summary
What we know
What remains open
Investigation map
Prior testing and coverage
Contradictions
Evidence
Next best action
What changed
```

Every material item must support a `Why this is here` affordance where provenance is available.

---

## 16. Health Investigation Audit UX

### Above-the-fold goal

Within seconds, the user should understand whether HerbaGraph found anything worth reviewing.

Example structure:

```text
YOUR HERBAGRAPH AUDIT

3 things worth reviewing

1. One prior test may not address the question you thought it did
2. One supplement amount is ambiguous
3. Two important evidence gaps remain open

WHAT WE KNOW
WHAT YOUR TESTS ACTUALLY ADDRESSED
WHAT REMAINS OPEN
THINGS THAT MAY NOT LINE UP
POTENTIAL LOW-VALUE REPEATS
YOUR NEXT BEST STEP
```

### Rules

- no sensational “we found the cause” language;
- no invented audit issues to create perceived value;
- no disease probability;
- every material audit card needs provenance and limitation;
- partial records must surface as limitations, not confident conclusions.

---

## 17. Today UX

Commercial MVP may initially focus on regimen adherence/exposure truth.

```text
TODAY

Morning                     [Taken all]
Magnesium 200 mg            [Taken] [Skip] [...]
B12 1000 mcg                [Taken] [Skip] [...]

Evening
...
```

Rules:

- `Taken all` creates atomic exposures under one IntakeSession;
- unchecked remains unconfirmed;
- Skip requires explicit user action;
- no streaks that encourage consumption;
- no “failed your regimen” language;
- missing logging remains missing.

---

## 18. Regimen UX

Required capabilities:

- empty state;
- add manual product;
- capture/upload placeholder only if backend capture is not ready;
- review field-level uncertainty;
- confirm identity;
- preserve `I don't know`;
- show current regimen;
- edit planned schedule via versioned regimen commands;
- inspect product/ingredient details;
- correct historical entries through append-only correction;
- view recent intake sessions;
- show Regimen Review issues.

### Consumer terminology

Use:

- My Regimen
- Today
- Taken
- Skipped
- Not recorded
- Needs confirmation
- Product details
- Why I take this
- Why this matters

Avoid exposing internal entity names unless in an advanced provenance view.

---

## 19. Next Best Action component

One reusable component should appear in My Case, Audit, Regimen, and later Signals/Experiments.

Example:

```text
NEXT BEST STEP

Confirm the magnesium amount on your product label.

Why this comes first
The current record cannot determine whether 500 mg refers to the compound weight or elemental magnesium. Resolving this changes the interpreted exposure with very little burden.
```

Do not show raw ranking scores to consumers by default.

---

# PART III — TEST AND VERIFICATION PROGRAM

## 20. Test philosophy

The MVP is not strong because many tests exist. It is strong when the tests prove the exact failure modes most likely to produce plausible-looking but false health intelligence.

All new scientific/data features require:

1. unit tests;
2. persistence/integration tests;
3. hostile-path tests;
4. authorization tests;
5. idempotency/replay tests;
6. correction/supersession tests;
7. stale-version tests where applicable;
8. end-to-end UAT path tests;
9. synthetic fixtures only;
10. exact command and result reporting in the PR.

---

## 21. Mandatory inherited hostile tests

These remain release blockers across every packet:

### Discovery truth

1. Normal EMG does not directly assess small-fiber function and cannot close that branch.
2. EMG is not attached to an unrelated biliary/upper-abdominal branch.
3. Unknown/unmatched test creates no unrelated evidence edge.
4. Replayed turn creates no duplicate semantic rows.
5. Non-informational follow-up creates no duplicate findings/gaps/evidence.
6. Correction supersedes the actual prior fact, active projection excludes the old fact, rebuild does not resurrect it.
7. Concurrent writers cannot create duplicate open branch/gap identities.
8. Safety escalation persists correctly across follow-up turns.
9. Malformed recoverable LLM extraction cannot corrupt durable Case state.
10. No user-facing output presents disease probability or diagnostic certainty.

---

## 22. Shared Reasoning Contract tests

### Identity

1. `magnesium` does not equal `magnesium_glycinate`.
2. `magnesium_oxide` evidence is not automatically applicable to `magnesium_glycinate`.
3. unknown magnesium product remains unknown.
4. compound mass and elemental amount remain distinct.
5. missing elemental fraction produces unknown, not zero.
6. parent evidence cannot silently transfer to child product/form.
7. botanical parent species cannot silently imply plant part/preparation.
8. proprietary blend missing amounts remain unknown.
9. synonym resolution does not override ambiguous identity without validation.
10. commerce metadata cannot alter canonical identity.

### Measurement/Coverage

1. serum B12 partially assesses B12-related state rather than closing all B12-relevant questions.
2. MMA limitations remain attached where applicable.
3. unrelated assay returns not-applicable/no edge.
4. missing measurement is not a normal result.
5. coverage classification is not conflated with result interpretation.

### Evidence

1. unresolved citation cannot become accepted claim evidence.
2. example/seed literature cannot enter unrelated Case evidence.
3. target form mismatch reduces/blocks applicability as configured.
4. route mismatch is explicit.
5. endpoint mismatch is explicit.
6. absence of direct evidence produces an uncertainty/limitation state, not a negative claim.

---

## 23. Health Investigation Audit tests

1. audit is deterministic for same Case version.
2. audit references only active/current Case state unless a historical section explicitly requests history.
3. audit does not resurrect superseded findings.
4. audit does not convert missing evidence into a negative finding.
5. audit does not generate `TEST_COVERAGE_MISMATCH` when coverage is unknown.
6. recalled “normal labs” remain unverified until source values are available.
7. unrelated workup is not described as inconclusive for an unrelated question.
8. no audit issue is generated solely because a commercial product exists.
9. audit may validly return no major mismatch.
10. every material audit finding contains at least one source/provenance reference or an explicit limitation explaining why one is unavailable.
11. stale Case version causes stale/reload response rather than mixed snapshot.
12. another user's Case cannot be retrieved by changing IDs.

### Logic test: waste detection

A repeated action can be labeled low-value only when the system can show:

- the prior action already adequately addressed the same question;
- no material Case change makes repetition newly informative;
- no safety/professional reason requires repetition;
- the claim is framed as decision-value guidance, not medical prohibition.

---

## 24. Regimen Truth tests

1. planned RegimenItem does not create ExposureEvent.
2. `Taken all` creates one IntakeSession and N separate ExposureEvents.
3. retrying `Taken all` with the same source command creates no duplicate IntakeSession or ExposureEvents.
4. same idempotency key with different semantics fails explicitly.
5. partial intake leaves unchecked items unconfirmed.
6. explicit Skip is distinct from unconfirmed.
7. correction 500 mg -> 250 mg preserves old exposure as superseded and projects 250 mg as active/current.
8. correction replay is idempotent.
9. product identity candidate cannot be used as confirmed exposure when policy requires confirmed identity.
10. proprietary blend does not invent ingredient quantities.
11. unknown form remains unknown after save/reload.
12. one user's exposure cannot be written/read through another user's Case.
13. timezone and occurred-at semantics survive round-trip.
14. transaction failure after session creation but before all child exposures cannot leave plausible partial success.
15. concurrent identical commands do not duplicate exposures.
16. Case version increments/coheres according to the accepted mutation contract.

---

## 25. Regimen Review tests

### Identity issues

1. unresolved form produces identity issue, not a guessed form.
2. ambiguous compound/elemental amount produces amount-semantics issue.
3. disclosed exact amount does not falsely produce ambiguity.

### Redundancy

1. exact duplicate ingredient can be detected.
2. parent/child relation alone does not prove clinically meaningful redundancy.
3. mechanism overlap without sufficient evidence must be qualified or omitted.

### Safety

1. known contraindication/safety relationship produces a governed issue.
2. unknown relationship does not produce `safe`.
3. safety issue outranks convenience/optimization issues.

### Objectives

1. regimen issue cannot claim goal conflict without explicit UserObjective/Constraint and supported relationship.
2. user-stated purpose remains user language, not system-proven efficacy.

### Interpretability

1. three material interventions started simultaneously produce low interpretability warning.
2. a single stable intervention with adequate baseline does not receive the same warning.
3. missing exposure times reduce interpretability but do not imply non-adherence.
4. confounder changes can reduce interpretability without creating causality claims.

---

## 26. Unified Next Best Action tests

1. safety override ranks first.
2. contraindicated candidate is ineligible.
3. completed/redundant candidate is ineligible.
4. non-addressing candidate cannot gain rank from irrelevant evidence.
5. commerce boost cannot alter rank.
6. resolving a high-impact identity ambiguity can outrank a costly new test when information value and burden support it.
7. rank is deterministic given identical candidates and ranker version.
8. alternatives remain inspectable.
9. ranker never emits an unavailable action whose prerequisites are unmet.
10. no candidate produces honest `no_candidate`/wait state rather than invented action.

### Decision-quality benchmark

Create a synthetic benchmark set where expert-reviewed expected ordering is recorded for at least:

- burning feet + normal EMG;
- RUQ concern + unrelated EMG;
- unverified recalled labs;
- ambiguous magnesium amount;
- multiple simultaneous supplement starts;
- resolved prior test with no reason to repeat;
- safety escalation case.

The benchmark must compare semantic ordering and exclusion behavior, not exact prose.

---

## 27. Declarative Discovery migration tests

1. existing gold cases produce equivalent active findings, gaps, branch state, safety state, and selected action before and after declarative-domain migration.
2. unknown domain does not silently borrow another domain's questions.
3. new domain overlay can be loaded without modifying orchestrator code when it uses existing discriminator schema.
4. invalid domain config fails closed at startup/test time.
5. duplicate discriminator codes are rejected.
6. missing required purpose/information-gain metadata is rejected.

---

## 28. Frontend tests

At minimum:

### Shell/navigation

1. consumer sees new information architecture under feature flag.
2. clinician patient context remains intact.
3. old routes either redirect or remain reachable during migration.
4. feature flag off preserves current shell.
5. mobile navigation exposes the same reachable modules.

### My Case

1. loading, empty, success, partial, stale, permission denied, API unavailable.
2. same Case version displayed across all sections.
3. `Why this is here` opens provenance without exposing raw PHI to telemetry.
4. superseded finding is absent from current view but available in history where intended.

### Audit

1. zero-issue audit renders honestly.
2. audit cards show limitation/provenance.
3. stale audit prompts refresh.
4. unsupported claims do not render.
5. mobile layout remains readable at 200% zoom.

### Regimen/Today

1. empty regimen.
2. confirmed item.
3. unknown identity.
4. proprietary blend.
5. planned but unconfirmed.
6. single taken action.
7. `Taken all`.
8. partial intake.
9. explicit skip.
10. correction.
11. network retry with idempotency.
12. stale Case conflict.
13. feature flag disabled.
14. owner-scope failure.
15. mobile touch targets >= 44x44.
16. keyboard navigation and focus restoration for dialogs/drawers.

---

## 29. API contract tests

Every mutating endpoint requires tests for:

- authentication missing;
- wrong owner/role;
- malformed payload;
- unsupported enum/state;
- missing idempotency key where required;
- stale expected Case version;
- duplicate/replay;
- conflicting semantic replay;
- database failure/rollback;
- audit/provenance creation;
- PHI-safe telemetry;
- feature disabled.

Every read endpoint requires:

- owner scoping;
- coherent Case version;
- explicit partial/empty states;
- no superseded-current contamination;
- no cross-user data leakage.

---

## 30. Migration verification

For every schema packet:

1. migrate empty PostgreSQL database to head;
2. migrate from currently supported prior head;
3. inspect constraints and indexes in live PostgreSQL, not only ORM metadata;
4. run downgrade only if downgrade is declared supported;
5. verify rollback plan before merge;
6. test concurrent semantic writes against PostgreSQL;
7. verify no default/sample/seed scientific data is inserted into real Cases by migration.

SQLite-only proof is insufficient for concurrency and PostgreSQL uniqueness claims.

---

## 31. Security/privacy verification

Mandatory checks:

- no PHI in fixtures, issue bodies, logs, analytics labels, screenshots, commit messages, or LLM evaluation artifacts;
- no secrets in repository or frontend bundle;
- owner scoping enforced server-side, never only in the frontend;
- every new export/share surface has explicit authorization behavior;
- product/research consent remains purpose-specific;
- future research use cannot silently reinterpret commercial data;
- telemetry uses event classes, not product names, symptoms, doses, free text, or patient identifiers;
- failed authorization does not leak existence of another user's resource.

Any material PHI/auth/consent expansion requires Founder approval and, when applicable, ADR update.

---

## 32. Scientific-output adversarial tests

Create adversarial fixtures where an LLM or candidate subsystem proposes:

- “This confirms neuropathy.”
- “Your normal EMG rules out nerve problems.”
- “Magnesium glycinate is better because oxide evidence showed X.”
- “500 mg magnesium glycinate equals 500 mg elemental magnesium.”
- “No logged dose means you skipped it.”
- “No interaction was found, so the combination is safe.”
- “Sleep improved after supplement X, therefore X caused the improvement.”
- fabricated PMID/source.
- seed/example literature attached to unrelated Case.
- user interpretation rewritten as system fact.

All must be rejected, downgraded, or rewritten into allowed bounded language before persistence/display.

---

## 33. End-to-end commercial gold cases

Create synthetic end-to-end fixtures that exercise real API/persistence/frontend boundaries, not helper-only tests.

### Gold Case A — Expensive prior-workup misunderstanding

User reports persistent burning feet, recalls “normal blood work,” later provides a normal EMG.

Expected:

- Case persists correctly;
- normal EMG does not close small-fiber branch;
- audit explains what EMG did/did not address;
- recalled normal labs remain unverified until uploaded;
- Next Best Action favors obtaining/reviewing missing evidence when appropriate;
- no diagnosis.

### Gold Case B — Unrelated workup contamination

User has RUQ/post-meal concern and an EMG in history.

Expected:

- EMG does not attach to biliary/upper-abdominal branch;
- audit does not label it inconclusive for the branch;
- next action is selected from relevant gaps only.

### Gold Case C — Magnesium identity/dose ambiguity

User adds “magnesium glycinate 500 mg” without clarity whether this is compound or elemental amount.

Expected:

- identity preserved;
- amount semantics unresolved;
- regimen review flags clarification;
- no invented elemental dose;
- Next Best Action may prioritize label confirmation;
- correction is append-only.

### Gold Case D — Multi-intervention attribution problem

User starts magnesium, glycine, and ashwagandha within three days for sleep.

Expected:

- regimen records all exact items;
- Regimen Review flags low experimental interpretability;
- system does not claim which intervention works;
- recommended action can be “hold variables stable / collect baseline” only when within allowed product policy.

### Gold Case E — No dramatic finding

User provides a coherent, well-documented Case with no supported mismatch.

Expected:

- audit honestly says no major supported mismatch found;
- next action may be wait/monitor/no-candidate;
- system does not manufacture value.

---

## 34. UAT acceptance protocol

Founder UAT should be performed on Railway UAT from `integration/agent` after exact-SHA review and green required checks.

### Functional UAT

For each gold case verify:

- user understands the current Case without developer explanation;
- uncertainty is visible;
- correction works;
- provenance is inspectable;
- no stale/mixed version appears;
- action hierarchy is obvious;
- mobile flow is usable;
- no hidden failure appears as success.

### Commercial UAT

With supervised external users, measure separately from scientific quality:

- time to first useful insight;
- percent receiving at least one supported decision-changing finding;
- percent who voluntarily add more records after first insight;
- artifact/share rate;
- return rate after new evidence arrives;
- willingness to pay for the Audit / ongoing Case;
- paid conversion;
- unprompted referral;
- clinician-share rate;
- qualitative quote: “What did HerbaGraph show you that you did not already know?”

Do not count compliments, free research participation, or survey enthusiasm as purchase evidence.

---

## 35. Performance and reliability targets

Initial targets for commercial MVP UAT:

- idempotent replay: 100% semantic equality on gold commands;
- cross-user authorization leakage: 0 tolerated;
- unsupported diagnostic claims in adversarial suite: 0 tolerated;
- invented citations: 0 tolerated;
- stale mixed-Case render in tested flows: 0 tolerated;
- duplicate ExposureEvent under retry/concurrency: 0 tolerated;
- correction resurrection after rebuild: 0 tolerated;
- audit finding provenance completeness: 100% for material findings or explicit limitation state;
- frontend fatal-error recovery path available for every new module;
- p95 read projection latency target defined and measured before commercial launch;
- p95 mutation latency target defined and measured before commercial launch.

Do not invent latency thresholds before measuring the UAT baseline. Record the baseline and then set a target that preserves a responsive user experience.

---

## 36. Feature flags

Recommended additive flags, following existing configuration conventions:

```text
CASE_OVERVIEW_V1
HEALTH_INVESTIGATION_AUDIT_V1
PERSONAL_EVIDENCE_REGIMEN_V1
REGIMEN_REVIEW_V1
UNIFIED_NEXT_ACTION_V1
DECLARATIVE_DISCOVERY_DOMAINS_V1
```

Rules:

- default off for materially new user-visible behavior unless the accepted repository convention explicitly says otherwise;
- UAT may enable flags;
- flag-off path remains tested;
- no production activation merely because code merged;
- flag removal occurs only after stabilization and Founder authorization.

---

## 37. Telemetry

Allowed PHI-safe event classes include:

```text
case_overview_loaded
health_audit_generated
health_audit_no_major_issue
health_audit_finding_opened
why_this_here_opened
regimen_add_started
identity_confirmation_required
regimen_item_confirmed
intake_session_confirmed
intake_partial_confirmed
exposure_correction_started
regimen_review_loaded
next_action_opened
version_conflict_seen
personal_evidence_api_failed
```

Never include symptoms, ingredient/product names, doses, free text, patient IDs, or raw evidence in analytics properties.

---

# PART IV — DELIVERY SEQUENCE FOR AI AGENTS

## 38. Required implementation order

Do not parallelize dependent truth-layer packets merely for speed.

### PR-1: Shared Reasoning Contracts + My Case projection

Scope:

- stable adapters/contracts;
- no science behavior rewrite;
- Case overview read model;
- initial frontend module registry/shell extraction as needed;
- My Case view behind feature flag.

Must preserve all Discovery gold cases.

### PR-2: Health Investigation Audit

Scope:

- deterministic audit projection;
- audit finding schemas;
- coverage mismatch/open-gap/unverified/identity issue types supported by existing data;
- audit frontend;
- `Why this is here` provenance;
- no Regimen dependency required for initial release.

### PR-3: Regimen Truth + IntakeSession

Scope:

- identity confirmation integration;
- RegimenVersion/RegimenItem;
- IntakeSession/ExposureEvent;
- Today + Regimen frontend;
- idempotency/correction/owner-scope tests.

### PR-4: Regimen Review + Objectives

Scope:

- UserObjective/ObjectiveConstraint;
- explainable regimen issue classes;
- identity/amount/redundancy/interpretability first;
- existing governed safety only where supported;
- no AI-generated broad interaction graph.

### PR-5: Unified Next Best Action

Scope:

- generic DecisionCandidate;
- Discovery candidate compatibility;
- identity/regimen candidate generators;
- single reusable frontend action component;
- benchmark ordering suite.

### PR-6: Declarative Discovery domain extraction

Scope:

- migrate existing gold domains to configuration;
- semantic-equivalence tests;
- no broad new condition coverage yet.

### STOP GATE

After PR-1 through PR-5 or PR-6, pause major new feature work and conduct commercial UAT.

Do not automatically proceed to Signals/Experiments/Attribution because they are architecturally planned. Continue only if commercial evidence or a specific strategic decision justifies them.

---

## 39. Agent work-order template

Every Grok implementation issue must include:

```text
HERBAGRAPH_HANDOFF
Task: HG-###
Status: READY_FOR_IMPLEMENTER
Target branch: integration/agent

Decision to change:

User-visible outcome:

Existing code to reuse:

Required behavior:

Invariants:

Red-first tests:

Hostile-path tests:

API/persistence contracts:

Feature flag:

Observability:

Migration/rollback:

UAT procedure:

Out of scope:

Founder decisions required:
```

The Implementer must inspect current code and cite reused paths in its implementation report.

---

## 40. Mandatory implementation report

```text
HERBAGRAPH_IMPLEMENTATION_REPORT
Task: HG-###
Status: READY_FOR_ARCHITECT
Branch:
Commit: <40-char SHA>
PR:

Implemented:

Reused existing capabilities:

Files changed:

Behavior changed:

Feature flags:

Tests added:

Tests run:
- command: exact result

PostgreSQL verification:

Migration:

Rollback:

Security/privacy impact:

Scientific/causal-boundary impact:

Known limitations:

Deferred work:

Questions:
```

False completion claims are automatic failure.

---

## 41. Architect/Judge review checklist

The exact-SHA reviewer must answer:

### Truth

- Can any path duplicate, contaminate, delete, or resurrect Case state?
- Can planned intervention become actual exposure without confirmation?
- Can missing become negative/zero/skipped?
- Can stale Case sections render together?

### Identity

- Can form/preparation/product differences be silently collapsed?
- Can compound and elemental dose semantics be conflated?
- Can parent evidence transfer beyond entitlement?

### Evidence

- Can unrelated evidence attach to a Case branch?
- Can seed/example evidence leak into production Case evidence?
- Can an unresolved citation render as accepted evidence?

### Causality

- Can temporal association become causal language?
- Can low-interpretability regimen changes produce confident attribution?

### Safety

- Can safety override be bypassed?
- Can unknown interaction become “safe”?

### Privacy/security

- Can owner scoping be bypassed?
- Is any PHI present in fixtures/logs/telemetry?

### UX

- Does partial/unknown/stale state remain visible?
- Does the frontend make confidence appear stronger than the backend contract?
- Is mobile/accessibility behavior acceptable?

Any critical failure is BLOCKING regardless of aggregate test count.

---

## 42. Commercial product gate after implementation

Do not judge success by feature completion alone.

The commercial MVP passes only when supervised real users demonstrate costly behavior consistent with value.

Strong evidence:

- payment;
- return usage after new evidence arrives;
- voluntary upload of additional records;
- clinician sharing;
- unprompted referral;
- paid continuation.

Weak evidence that must remain separate:

- compliments;
- survey enthusiasm;
- free trial completion;
- research volunteering;
- clicks;
- time in app without a decision-changing outcome.

The product should aim to create this reaction:

> “HerbaGraph showed me something important about my existing health investigation that I had not understood, explained why it mattered, and gave me a better next step without pretending to diagnose me.”

That is the commercial MVP gate this execution plan is designed to test.
