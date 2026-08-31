# HerbaGraph Reasoning Core Architecture

**Status:** Authorized architecture proposal
**Issue:** #65 amendment
**Scope:** Extract and formalize shared intelligence from Discovery into platform infrastructure
**Context:** Personal Evidence frontend IA remap complete. Next: align backend architecture with the new product structure.

---

## Executive summary

The most durable enterprise value in HerbaGraph is not the "Ask" conversation surface. It is the reasoning infrastructure that Ask exercises: exact substance identity, measurement coverage semantics, evidence applicability enforcement, investigation state tracking, and next-best-action selection.

That infrastructure currently lives in `app/discovery/` and is implicitly owned by the Discovery feature. The refactor proposed here formally extracts it into a shared `app/intelligence/` namespace, establishes it as first-class platform infrastructure, and defines how both Discovery and Personal Evidence consume the same governed contracts.

**The moat is not "HerbaGraph knows about magnesium."**
The moat is: *HerbaGraph maintains exact identity, measurement semantics, evidence applicability, investigation state, and causal uncertainty as governed, provenance-linked graph state — and can answer questions about any of them deterministically.*

---

## 1. What already exists in the codebase

Before proposing a refactor, we audit what is already built and whether it is already architected as a service.

### 1.1 Identity Engine — `app/discovery/composition.py`

**Status: Ready for extraction.** This is the cleanest existing engine.

```python
# 10-layer composition ontology
KNOWN_LAYERS = frozenset({
    "concept", "subtype", "phenotype", "part", "form",
    "preparation", "product_batch", "exposure", "assay",
    "measured_composition", "claim",
})

# Critical invariants already enforced
claim_transfers(source, target, relation)
# → False when relation is "supports_outcome_in_population" or "contains_measured"
# → False when src is product_batch and dst is not product_batch
# → False when src is preparation and dst is phenotype or concept
# → False when a "does_not_address" relation exists

assay_does_not_close_parent(assay, parent)
# → True when assay "partially_assesses" the parent
# An assay cannot close the parent concept by identity alone.

forms_not_ranked_on_generic_effectiveness(left, right)
# → True when left != right
# Different forms cannot share one effectiveness score.

elemental_amount(form_code, compound_mass_mg)
# → {"elemental_mg": ..., "unknown": False} when fraction is known
# → {"elemental_mg": None, "unknown": True} when fraction is unknown

synonym_to_code(name)        # human name → canonical code
identity_of(code)            # code → identity dimensions dict
load_composition_graph()     # versioned JSON graph
overlay_uses_existing_layers(overlay)  # extensibility check
```

**Seeded graph:** 29 concepts, 14 typed relations, 3 provenance sources (composition-graph-v1).
Demonstrates all 10 layers with B12, magnesium, biotin, grape, and salt examples.
The `claim_transfers()` function already prevents:
- magnesium oxide evidence → magnesium glycinate
- preparation evidence → every parent/child variation
- batch evidence → every category-level claim

**Identity dimensions defined** (12 dimensions):
`parent`, `chemical_identity`, `form`, `source_organism`, `part`, `preparation`, `matrix`, `formulation`, `route`, `dose`, `release_profile`, `product_batch`, `assay`, `synonyms`, `jurisdiction`, `evidence_context`

**Overlay extensibility already demonstrated:** `composition_graph_extensibility_folate.json` adds folate/vitamin B9 using only existing layers, with `overlay_uses_existing_layers()` verifying no schema change is required. ADR-MVP-007 governs this.

### 1.2 Measurement Engine — `app/discovery/coverage_governor.py` + `coverage_catalog.py`

**Status: Ready for extraction.** Fully structured, versioned, policy-governed.

```python
# Typed coverage relations — not just "covers / doesn't cover"
CoverageRelation:
  DIRECTLY_ASSESSES        → test fully addresses a concept
  PARTIALLY_ASSESSES       → test only partially addresses (limitation stated)
  INDIRECTLY_INFORMS       → can indirectly inform
  DOES_NOT_DIRECTLY_ASSESS → test does not address this concept
  NOT_APPLICABLE           → catalogued as not applicable
  UNKNOWN                  → no coverage relation catalogued

# Core API
assess_coverage(test_code, investigation_concept, protocol_id=None)
→ CoverageAssessment(
    relation: CoverageRelation,
    explanation: str,          # human-readable, not a hardcoded phrase
    test_code: str,
    concept: str,
    protocol_code: str | None,
    rule_version: str,
    provenance: str,
  )

explain_relation(test_name, concept_label, relation)
→ "{test} only partially assesses {concept}."  # template-driven

# Seeded catalog: 9 tests, 7 concepts, 9 typed rules
# Tests: EMG/NCS, MRI brain/cervical/lumbar, skin punch biopsy/IENFD, RUQ ultrasound
# Relations cover large-fiber, small-fiber, structural brain, biliary, blood counts
# "partially_assesses" appears on: serum B12 → vitamin B12 (neurologic limitation)
#                                  MMA → vitamin B12 (kidney nonspecificity)
#                                  homocysteine → vitamin B12 (nonspecific)
```

**Coverage is epistemic completeness, not disease probability.** This distinction is already documented in `map.py`.

### 1.3 Evidence Applicability Engine — `composition.py` + `evidence_interpreter.py` + `literature.py`

**Status: Partial — composition engine is ready; literature layer needs extraction.**

The `composition.py` `claim_transfers()` function is the applicability kernel. It is currently called by the literature module. The next step is to make it a first-class synchronous API rather than a side effect of evidence retrieval.

### 1.4 Investigation Engine — `app/discovery/guide.py`

**Status: Structured but LLM-coupled. Ready for contract formalization.**

```python
DiscoveryTurnPlan (Pydantic model):
  reported_facts: list[CandidateFinding]     # symptom, context, assessment
  patient_interpretations: list[str]          # verbatim
  timeline_updates: list[str]                 # verbatim
  prior_workup: list[dict]                    # test + result
  branch_updates: list[BranchUpdateCandidate] # code + operation + rationale
  evidence_gap_updates: list[dict]
  contradictions: list[str]
  corrections: list[dict]
  action_candidates: list[NextActionCandidate]
  recommended_next_action: NextActionCandidate | None
  problem_representation: str
  missing_dimensions: list[str]               # unresolved discriminators
  unresolved_dimensions: list[str]
  literature_queries: list[str]
  uncertainty_updates: list[str]
  safety_flags: list[str]
```

The `guide.py` module parses a user turn into a structured `DiscoveryTurnPlan`. This is the Investigation Engine's output contract. The LLM is the implementation detail.

### 1.5 Next-Best-Action Engine — `app/discovery/actions.py` + `orchestrator.py`

**Status: Structured. Ready for formalization as a separate service.**

```python
CatalogQuestion:
  code, prompt, closes, kind, purpose, options,
  interaction: str, gain: float  # expected information gain

QUESTIONS: tuple[CatalogQuestion, ...]  # 8 seed questions in current catalog

NextAction:
  type: str           # ask_question | summarize | clarify | retrieve_evidence |
                      # request_record | show_investigation_map | show_safety_message
  objective: str      # why this action
  question_id: str | None
  prompt: str | None
  interaction: dict | None   # type: single_select, options: [...]
  score: float        # ranking score

rank_next_actions(actions, context)  # already extracted as a function
generate_actions(...)                 # generates candidates from guide plan
select_action(...)                   # picks the highest-scored
```

`orchestrator.py` orchestrates: Case mutation → action selection → evidence retrieval → response composition. The `TurnResult` dataclass is the output contract.

### 1.6 Scientific Governor — `app/discovery/scientific_output.py` + `coverage_governor.py` + `literature.py`

**Status: Already structured as a governor pattern.**

The Scientific Governor is a synchronous validation layer that runs before any output is verbalized or stored. It governs:
- Language: no disease claims, no causal language without sufficient evidence
- Coverage: test limitations are stated, not omitted
- Evidence: applicability limits are attached, not stripped
- Safety: `safety_status` in `TurnResult` governs triage level (S0–S4)

### 1.7 Idempotency / Correction — `app/discovery/identity.py`

**Status: Ready for cross-service promotion.**

```python
finding_identity_key(case_id, name, value, source_event_id)
# SHA-256 of normalized material → stable key
# Enables deduplication: same finding in same turn → same key

gap_identity_key(case_id, branch_code, gap_code, source_event_id)
evidence_identity_key(case_id, branch_code, workup_key, relationship, version)
finding_source_event_id(source, name, value)
```

This is the append-only correction foundation. All Personal Evidence modules need these same semantics: corrections supersede, they do not delete.

### 1.8 What needs work

The following Discovery modules contain **hardcoded symptom-specific logic** that is technical debt, not enterprise infrastructure:

- `orchestrator.py` lines 33–42: `_PATTERN_UNKNOWNS` and `_GI_UNKNOWNS` tuples with hardcoded discriminator names (laterality, distribution, weakness, meal_relation, nausea)
- `map.py` lines 20–21: `_PATTERN_UNKNOWNS` with the same hardcoded strings, used in `unknowns_from_facts()`
- Evidence of bespoke logic around RUQ vs. epigastric location

These were reasonable for the MVP. They must not become the permanent architecture.

---

## 2. Target architecture: `app/intelligence/`

The refactor creates a new top-level package. Nothing in `app/discovery/` is deleted immediately. Modules are migrated progressively by import redirection.

```
app/
  intelligence/                    # NEW: shared reasoning infrastructure
    __init__.py
    identity/                      # Identity Engine
      __init__.py
      graph.py                    # composition.py moved and renamed
      layers.py                   # KNOWN_LAYERS, IDENTITY_DIMENSIONS
      transfers.py                # claim_transfers(), forms_not_ranked_*()
      assays.py                   # assay_does_not_close_parent()
      dose.py                     # elemental_amount()
      resolution.py               # synonym_to_code(), identity_of()
      overlays.py                 # overlay_uses_existing_layers(), merge_overlay()
    measurements/                 # Measurement Engine
      __init__.py
      catalog.py                  # coverage_catalog.py
      governor.py                 # coverage_governor.py
      explain.py                  # explain_relation()
      relations.py                # CoverageRelation enum, RELATION_TEMPLATES
    evidence/                     # Evidence Applicability Engine
      __init__.py
      applicability.py            # claim_transfers() wrapped as API
      interpreter.py               # evidence_interpreter.py (extract from discovery/)
    investigation/                # Investigation Engine
      __init__.py
      guide.py                    # guide.py extracted
      plan.py                     # DiscoveryTurnPlan, CandidateFinding, etc.
      discriminators.py           # NEXT: InvestigationDomain, Discriminator schema
      coverage.py                  # concepts_for_branch(), branch_concepts
    actions/                      # Next-Best-Action Engine
      __init__.py
      catalog.py                  # CatalogQuestion, QUESTIONS
      ranker.py                   # rank_next_actions()
      generator.py                # generate_actions()
      selector.py                 # select_action()
    safety/                       # Scientific Governor
      __init__.py
      governor.py                 # assess_safety(), safety_findings_to_facts()
      output.py                   # ScientificItem, validate_scientific_output()
      policies/                   # consumer_claims_policy.md as structured rules
    identity_mutation/             # Idempotency / Correction primitives
      __init__.py
      keys.py                     # identity.py extracted
    data/
      composition_graph_v1.json   # moved from discovery/data/
      composition_graph_extensibility_folate.json
      coverage_catalog_v1.json    # moved from discovery/data/
  discovery/                      # CONSUMER of app/intelligence/
    composition.py                # imports from app/intelligence/identity/graph.py
    coverage_catalog.py           # imports from app/intelligence/measurements/
    coverage_governor.py          # imports from app/intelligence/measurements/
    # ... all other modules updated to import from intelligence
  personal_evidence/              # CONSUMER of app/intelligence/
    regimen.py                    # imports identity for product resolution
    signals.py                   # imports measurements for coverage evaluation
    experiments.py                # imports actions, evidence
    attribution.py               # imports evidence applicability
    # ... etc.
```

**Import redirection during migration (no breaking changes):**

During Phase 1, `app/discovery/composition.py` becomes a thin shim:
```python
# app/discovery/composition.py  — TEMPORARY SHIM
from app.intelligence.identity.graph import load_composition_graph
from app.intelligence.identity.transfers import claim_transfers
# re-export everything under the original names
```

All consumers continue to import from `app.discovery.composition`. Once all callers are updated, the shim is removed.

---

## 3. Engine API contracts

### 3.1 Identity Engine — `app/intelligence/identity/`

```python
# graph.py
load_composition_graph(path: str | None = None) → dict
load_extensibility_overlay() → dict
overlay_uses_existing_layers(overlay: dict, base: dict | None = None) → bool
merge_overlay(base: dict, overlay: dict) → dict

# transfers.py
claim_transfers(source_code: str, target_code: str, relation: str,
                graph: dict | None = None) → bool
forms_not_ranked_on_generic_effectiveness(left: str, right: str,
                                          graph: dict | None = None) → bool
assay_does_not_close_parent(assay_code: str, parent_code: str,
                           graph: dict | None = None) → bool

# resolution.py
synonym_to_code(name: str, graph: dict | None = None) → str | None
identity_of(code: str, graph: dict | None = None) → dict
concept(code: str, graph: dict | None = None) → dict | None
relations_from(code: str, graph: dict | None = None) → list[dict]

# dose.py
elemental_amount(*, form_code: str, compound_mass_mg: float,
                graph: dict | None = None) → dict
# Returns: {"compound_mass_mg": float, "elemental_mg": float | None, "unknown": bool}

# layers.py
KNOWN_LAYERS: frozenset[str]
IDENTITY_DIMENSIONS: tuple[str, ...]
INHERITANCE_FORBIDDEN: frozenset[str]
SEED_SOURCE_IDS: frozenset[str]

# Future extensions (Phase 3+):
# resolve_product_name(name: str) → ProductIdentityCandidate
# elemental_fraction_for_form(form_code: str) → float | None
```

### 3.2 Measurement Engine — `app/intelligence/measurements/`

```python
# governor.py
@dataclass(frozen=True)
class CoverageAssessment:
    relation: CoverageRelation
    explanation: str           # template-driven, not LLM-generated
    test_code: str
    concept: str
    protocol_code: str | None
    rule_version: str
    provenance: str

assess_coverage(
    test_code: str,
    investigation_concept: str,
    protocol_id: str | None = None,
) → CoverageAssessment

# catalog.py
load_catalog(path: str | None = None) → CoverageCatalog
catalog_version() → str
tests_by_normalized_alias() → dict[str, list[CatalogTest]]
test_code_for_finding(name: str) → str | None
concepts_for_branch(branch_or_code: str) → tuple[str, ...]
concept_label(code: str) → str
test_name(code: str) → str

# relations.py
CoverageRelation: enum  # DIRECTLY_ASSESSES | PARTIALLY_ASSESSES | ...
RELATION_TEMPLATES: dict[str, str]
```

**How Personal Evidence consumes the Measurement Engine:**

When Signals evaluates whether a CGM reading is relevant to an insulin-sensitivity objective:
```python
assessment = assess_coverage("cgm_postprandial", "insulin_sensitivity")
# → CoverageAssessment(relation=PARTIALLY_ASSESSES,
#                      explanation="CGM postprandial glucose is a relevant metabolic
#                      signal but does not fully establish insulin sensitivity,
#                      HbA1c change, or long-term metabolic effect.")
```

When Today evaluates whether an HRV observation addresses a "reduce stress" objective:
```python
assessment = assess_coverage("hrv", "perceived_stress")
# → CoverageAssessment(relation=DOES_NOT_DIRECTLY_ASSESS,
#                      explanation="HRV partially assesses physiological autonomic
#                      state. It does not directly measure perceived stress,
#                      anxiety, or clinical stress symptoms.")
```

### 3.3 Evidence Applicability Engine — `app/intelligence/evidence/`

```python
# applicability.py
@dataclass
class ApplicabilityResult:
    applicable: bool
    reasons: list[str]           # human-readable limitation explanations
    blocked_by: list[str]        # relation types that blocked transfer
    provenance: str
    graph_version: str

def evaluate_applicability(
    claim: str,                  # human-readable claim being transferred
    source_code: str,            # concept code from the study
    target_code: str,            # concept code of the user's actual product
    relation: str,               # evidence relation type
    population: str | None = None,
    outcome: str | None = None,
    route: str | None = None,
    graph: dict | None = None,
) → ApplicabilityResult
```

**Example:** Is magnesium oxide evidence applicable to a user's magnesium glycinate use?
```python
result = evaluate_applicability(
    claim="Magnesium improves sleep quality.",
    source_code="magnesium_oxide",
    target_code="magnesium_glycinate",
    relation="supports_outcome_in_population",
)
# → ApplicabilityResult(applicable=False,
#     reasons=["Different endpoints cannot share a generic effectiveness score.",
#              "oxide evidence does not transfer to every magnesium form."],
#     blocked_by=["generic_effectiveness_mismatch", "form_transfer_forbidden"])
```

### 3.4 Investigation Engine — `app/intelligence/investigation/`

```python
# plan.py — Pydantic models (extracted from guide.py)
class DiscoveryTurnPlan(BaseModel):
    reported_facts: list[CandidateFinding]
    patient_interpretations: list[str]
    timeline_updates: list[str]
    prior_workup: list[dict]
    branch_updates: list[BranchUpdateCandidate]
    evidence_gap_updates: list[dict]
    contradictions: list[str]
    corrections: list[dict]
    safety_flags: list[str]
    action_candidates: list[NextActionCandidate]
    recommended_next_action: NextActionCandidate | None
    problem_representation: str
    missing_dimensions: list[str]
    literature_queries: list[str]
    uncertainty_updates: list[str]

# discriminators.py — Phase 2 declarative structure
@dataclass
class Discriminator:
    code: str
    question: str
    closes: str               # branch code this resolves
    purpose: str              # why this discriminator matters
    kind: str                 # safety | discriminating | baseline
    interaction: str          # yes_no | single_select | ...
    options: tuple[str, ...]
    expected_gain: float      # information gain estimate
    evidence_source: str | None
    safety_implications: str | None

@dataclass
class InvestigationDomain:
    domain_code: str           # e.g., "upper_gi_discomfort"
    display_name: str
    discriminators: tuple[Discriminator, ...]
    coverage_concepts: tuple[str, ...]  # concepts this domain addresses
    required_discriminators: tuple[str, ...]  # minimum set for completeness
```

The current hardcoded `_PATTERN_UNKNOWNS` and `_GI_UNKNOWNS` in `orchestrator.py` and `map.py` become the first entries in a declarative `investigation_domains.json` catalog.

### 3.5 Next-Best-Action Engine — `app/intelligence/actions/`

```python
# catalog.py
@dataclass(frozen=True)
class CatalogQuestion:
    code: str
    prompt: str
    closes: str
    kind: str
    purpose: str
    options: tuple[str, ...]
    interaction: str
    gain: float

QUESTIONS: tuple[CatalogQuestion, ...]

# ranker.py
def rank_next_actions(
    actions: list[NextAction],
    context: ActionRankingContext,
) → list[NextAction]:
    # Returns actions sorted by score descending
    # Score incorporates: expected_information_gain, urgency, safety, recency

# The Personal Evidence use case:
# When Today shows no recent sleep observations:
#   → action: "Record three more nights of baseline sleep."
#   → expected_information_gain: HIGH
#   → burden: LOW
#   → type: request_record
```

### 3.6 Scientific Governor — `app/intelligence/safety/`

```python
# governor.py
def assess_safety(facts: dict, plan: DiscoveryTurnPlan | None) → SafetyAssessment
# Returns: safety_status (S0–S4), safety_findings, escalation_required

# output.py
def validate_scientific_output(
    output: str,
    analysis: AttributionAnalysis | None,
    context: ScientificContext,
) → ScientificValidationResult:
# Rejects: disease claims, causal language without sufficient evidence,
#          ungoverned supplement recommendations without evidence basis
```

---

## 4. Four-phase refactor plan

### Phase 1 — Extract shared intelligence (4–6 engineering days)

**Goal:** Create `app/intelligence/` as a working copy. All existing Discovery imports continue to function. No Personal Evidence modules change behavior.

**Actions:**
1. Create `app/intelligence/identity/`, `measurements/`, `actions/`, `safety/`, `identity_mutation/` directories with `__init__.py` files.
2. Move and rename: `composition.py` → `identity/graph.py`, `coverage_catalog.py` → `measurements/catalog.py`, `coverage_governor.py` → `measurements/governor.py`, `identity.py` → `identity_mutation/keys.py`, `actions.py` → `actions/catalog.py`.
3. Add `app/discovery/composition.py` shim that re-exports from `app.intelligence.identity.graph`.
4. Add `app/discovery/coverage_catalog.py` shim.
5. Add `app/discovery/coverage_governor.py` shim.
6. Add `app/discovery/actions.py` shim.
7. Add `app/discovery/identity.py` shim.
8. Run full test suite. All existing tests must pass. No Discovery behavior changes.
9. Document shim removal schedule in ADR.

**Exit criteria:** All Discovery tests pass. All Personal Evidence fixture tests pass. Shims in place.

### Phase 2 — Make Discovery declarative (5–8 engineering days)

**Goal:** Replace hardcoded symptom logic in `orchestrator.py` and `map.py` with a declarative investigation domain catalog. The hardcoded `_PATTERN_UNKNOWNS` and `_GI_UNKNOWNS` are the first migration target.

**Actions:**
1. Create `app/intelligence/investigation/data/investigation_domains_v1.json`.
2. Seed it with the 8 existing `CatalogQuestion` entries and the current discriminator sets (neurological pattern, GI case).
3. Extract `DiscoveryTurnPlan`, `CandidateFinding`, etc. from `guide.py` into `app/intelligence/investigation/plan.py`.
4. Update `guide.py` to import from `app.intelligence.investigation.plan` and `app.intelligence.investigation.discriminators`.
5. Update `orchestrator.py` to import discriminators from the JSON catalog instead of hardcoded tuples.
6. Update `map.py` similarly.
7. Add `InvestigationDomain` and `Discriminator` Pydantic models in `discriminators.py`.
8. Add extensibility test: `test_new_domain_uses_existing_layers()` verifying a new domain can be added without schema change.

**What this fixes:**
```python
# BEFORE (technical debt in orchestrator.py)
_PATTERN_UNKNOWNS = ("laterality", "distribution", "weakness",
                     "temperature sensation", "emg testing")
_GI_UNKNOWNS = ("pain_location", "episode_duration",
                 "meal_relation", "nausea")

# AFTER (declarative in investigation_domains_v1.json)
{
  "domain_code": "peripheral_neuropathy_pattern",
  "discriminators": [
    {"code": "laterality", "question": "...", "kind": "discriminating", "gain": 0.88},
    ...
  ]
}
```

**Exit criteria:** All Discovery tests pass. New domain extensibility test passes. No hardcoded symptom strings remain in orchestrator.py or map.py.

### Phase 3 — Unify next-best-action (5–7 engineering days)

**Goal:** One decision layer operating across Investigation, Identity, Regimen, Observation, Experiment, and Attribution.

**Actions:**
1. Extract `rank_next_actions()` from `app/discovery/ranker.py` into `app/intelligence/actions/ranker.py`.
2. Define `ActionRankingContext` as a Pydantic model that can accept context from any domain (investigation, PE, etc.).
3. Add `app/intelligence/actions/context.py` with domain-specific context builders:
   - `investigation_context(case_state)` → `ActionRankingContext`
   - `regimen_context(regimen_version, open_questions)` → `ActionRankingContext`
   - `experiment_context(protocol, adherence_to_date)` → `ActionRankingContext`
4. Update `app/discovery/orchestrator.py` to call `rank_next_actions(investigation_context(case_state))`.
5. Wire Personal Evidence modules to call `rank_next_actions(regimen_context(...))`.
6. Define the unified `NextAction.type` taxonomy so action types are consistent across all domains.

**Exit criteria:** One `rank_next_actions()` function used by all consumers. Personal Evidence modules produce ranked next actions from the same engine.

### Phase 4 — Expose governed enterprise interfaces (8–12 engineering days)

**Goal:** Internal APIs stabilize before external exposure.

**Internal API contracts (deployable on UAT behind auth):**

```text
POST /api/v1/intelligence/identity/resolve
Body: { "name": "magnesium glycinate 300mg" }
→ { "code": "magnesium_glycinate", "form": "glycinate",
    "elemental_fraction": 0.141, "confidence": "high",
    "synonyms": [...], "layer": "form" }

POST /api/v1/intelligence/evidence/applicability
Body: { "source_code": "magnesium_oxide",
        "target_code": "magnesium_glycinate",
        "relation": "supports_outcome_in_population",
        "outcome": "sleep_quality" }
→ { "applicable": false, "reasons": [...],
    "blocked_by": ["generic_effectiveness_mismatch"] }

POST /api/v1/intelligence/measurements/coverage
Body: { "test_code": "cgm_postprandial",
        "concept": "insulin_sensitivity" }
→ { "relation": "partially_assesses",
    "explanation": "CGM postprandial glucose is a relevant metabolic signal
                    but does not fully establish insulin sensitivity.",
    "rule_version": "coverage-catalog-v1" }

GET  /api/v1/intelligence/investigation/domains
→ { "domains": [{"code": "peripheral_neuropathy_pattern", ...}, ...] }

GET  /api/v1/intelligence/actions/next
Query: ?context=investigation&case_id=...
→ { "action": {"type": "ask_question", "prompt": "...",
               "score": 0.86, "gain": 0.88}, ... }

POST /api/v1/intelligence/regimen/assess
Body: { "regimen_version_id": "...", "case_id": "..." }
→ { "relationships": [...], "conflicts": [...],
    "unresolved_relationships": [...] }
```

**Governance on all endpoints:**
- Owner/role authorization
- Request fingerprinting (no PHI in broker metadata)
- Non-PHI telemetry (latency, error rates, resolution rates)
- Rate limiting
- Explicit error responses (no 500 with raw traceback)

**External exposure:** Requires separate commercial terms, API key management, rate tiering, and SLA — out of scope for this phase. Phase 4 ships the internal contracts.

---

## 5. How Personal Evidence consumes the Reasoning Core

The five Personal Evidence modules are the first non-Discovery consumers of `app/intelligence/`.

| PE Module | Engine Consumed | What It Asks |
|---|---|---|
| **Regimen** | Identity Engine | What exactly is this product? Is elemental amount calculable? |
| **Today** | Measurement Engine | Does this observation address the user's objective? |
| **Signals** | Measurement Engine + Evidence Applicability | Is this exposure relevant to this outcome? Does the evidence transfer? |
| **Experiments** | Measurement Engine + Evidence Applicability + NBA | What measurement addresses the hypothesis? Does the intervention evidence apply? What next action? |
| **What I Learned** | Evidence Applicability + Scientific Governor | Does this evidence apply to the exact intervention? Is this wording allowed? |
| **Passport** | All engines | Projection only — reads governed state, produces exportable summary |

**Example — Signals using Evidence Applicability:**

```python
# app/personal_evidence/signals.py (Phase 3 when backend is wired)
from app.intelligence.evidence.applicability import evaluate_applicability

def check_signal_applicability(signal: CandidateSignal,
                                exposure: ExposureEvent,
                                observation: ObservationEvent) -> SignalEligibility:
    # Does the exposure's product evidence apply to the observed outcome?
    result = evaluate_applicability(
        claim=signal.observed_relationship,
        source_code=exposure.product_form_code,
        target_code=observation.concept_code,
        relation="supports_outcome_in_population",
        outcome=observation.concept_code,
    )
    if not result.applicable:
        return SignalEligibility(
            eligible=False,
            reason="Evidence from " + exposure.product_name +
                   " does not transfer to the observed outcome. " +
                   "; ".join(result.reasons),
            blocked_by=result.blocked_by,
        )
    return SignalEligibility(eligible=True, reason=None, blocked_by=[])
```

---

## 6. Ontology scaling strategy

The user asked: "How do I add every vitamin, mineral, and herb without creating an unmanageable JSON pile?"

**Answer: An ontology + ingestion pipeline, not manual cataloging.**

The architecture already demonstrates the pattern:
1. `KNOWN_LAYERS` defines the schema (10 layers, fixed)
2. `overlay_uses_existing_layers()` verifies new domains use only existing layers (no schema change)
3. `merge_overlay()` composes new domains into the graph without modifying the base
4. ADR-MVP-007 governs the change process

**Ontology scaling approach:**

```
Canonical Biological Identity Ontology (CBIO)

Layer 1: Nutrient / Species / Compound concept
  ↓ form (chemical form, salt, isomer)
  ↓ preparation (extraction, chelation, matrix)
  ↓ product (brand, lot, batch)

For each concept:
  - synonyms
  - elemental_fraction (where applicable)
  - evidence_applicability_relations
  - relevant_assays
  - known_interference
  - cofactor_relations
```

**Ingestion pipeline (Phase 4+):**
1. Curated source → structured overlay JSON (human review required for each new concept)
2. `overlay_uses_existing_layers()` test runs automatically
3. If test passes: merge into graph, new concepts available across all engines
4. If test fails: new layer required → requires ADR decision

This means HerbaGraph does not need to "know about" every herb immediately. It needs a repeatable, governed process for adding them. The 29 concepts in the current graph are the **proof of concept**. The scaling mechanism is the overlay pipeline.

---

## 7. Technical debt addressed

### 7.1 Hardcoded symptom discriminators

**Location:** `orchestrator.py` lines 33–42, `map.py` lines 20–21.

**Problem:** If HerbaGraph says "I know your test scenario," the enterprise story collapses.

**Solution:** Phase 2 replaces hardcoded tuples with `investigation_domains_v1.json`. Adding a new symptom domain becomes adding a JSON entry, not editing Python.

**Migration:**
```python
# orchestrator.py — BEFORE
from app.discovery.map import _PATTERN_UNKNOWNS
if facts.get("emg testing") in {...}:
    _add("Ask whether EMG / NCS was already done", ...)

# orchestrator.py — AFTER
from app.intelligence.investigation.discriminators import discriminators_for_domain
discriminators = discriminators_for_domain(domain_code)
for disc in discriminators:
    if disc.kind == "discriminating" and facts.get(disc.code) is None:
        _add(disc.question, disc.purpose)
```

### 7.2 Bespoke RUQ vs. epigastric location logic

**Location:** Presumed in `map.py` or `guide.py` reasoning branches.

**Solution:** Encoded as `Discriminator` entries in the relevant `InvestigationDomain` in `investigation_domains_v1.json`. The discriminator question is data, not code.

---

## 8. Anti-patterns prohibited

These patterns must not emerge as the refactor progresses:

1. **"We can just add this to Ask."** — New capabilities go into the appropriate engine, then Ask (and Personal Evidence) consumes the engine. Ask is a consumer, not the owner.

2. **"The LLM knows this."** — Identity resolution, coverage assessment, and evidence applicability are deterministic functions. The LLM may assist in drafting structured input, but the governing function is a pure function with no model dependency.

3. **"No documented interaction = safe."** — The RegimenIntelligence taxonomy explicitly includes `unknown` and `no_documentation` as distinct from `compatible`. The UI must never render them as green or neutral. The Scientific Governor must enforce this.

4. **"One effectiveness score for all forms."** — `forms_not_ranked_on_generic_effectiveness()` enforces this invariant in the Identity Engine. Any code path that computes or displays a cross-form effectiveness score must go through this function.

5. **"Batch evidence applies to the category."** — `claim_transfers()` enforces this. The Scientific Governor must reject any output that violates it.

6. **"We can infer the missing value."** — Missing is never zero. `ObservationEvent` explicitly supports `missed`, `skipped`, `unknown`, and `not_applicable` types. No imputation.

---

## 9. Dependency direction (contract)

```
app/intelligence/  ← app/discovery/  (Phase 1 shim, then direct imports)
                 ← app/personal_evidence/
                 ← app/api/v1/

app/discovery/  → app/intelligence/  (consumer after Phase 1)
app/personal_evidence/  → app/intelligence/  (consumer)

app/api/v1/  → app/intelligence/  (Phase 4 enterprise API)
```

`app/intelligence/` has **no upward dependencies**. It is a pure infrastructure package with no FastAPI routes, no database models, and no LLM calls. Its functions are synchronous and deterministic (except for the LLM-free identity/measurement/evidence engines; the Investigation Engine's LLM coupling is isolated in `guide.py`).

---

## 10. Migration ordering for Personal Evidence

Since the Personal Evidence frontend IA remap is now live, the backend integration must follow this sequence:

1. **Regimen → Identity Engine** (Phase 1): When product name capture is wired, `synonym_to_code()` and `elemental_amount()` resolve the product before the user confirms identity.

2. **Today → Measurement Engine** (Phase 3): When observation recording is wired, `assess_coverage()` evaluates whether each observation addresses the user's stated objectives.

3. **Signals → Measurement Engine + Evidence Applicability** (Phase 3–4): When candidate signals are generated, `evaluate_applicability()` checks whether the exposure evidence transfers to the observed outcome.

4. **What I Learned → Evidence Applicability + Scientific Governor** (Phase 4): When attribution analysis runs, `evaluate_applicability()` + `validate_scientific_output()` produce governed output with explicit limitations.

5. **Passport → All engines** (Phase 4): When Passport is generated, it reads from governed state produced by all upstream engines. No new reasoning in Passport — only projection.

---

## 11. Exit criteria for each phase

**Phase 1 complete when:**
- [ ] `app/intelligence/` package exists with all 6 engine directories
- [ ] All Discovery imports continue to resolve (shims in place)
- [ ] Full test suite passes (no regressions)
- [ ] `composition_graph_v1.json` and `coverage_catalog_v1.json` moved to `app/intelligence/data/`
- [ ] ADR written: "Intelligence package as shared infrastructure"

**Phase 2 complete when:**
- [ ] `investigation_domains_v1.json` exists with all 8 existing discriminators
- [ ] No hardcoded symptom strings in `orchestrator.py` or `map.py`
- [ ] `test_new_domain_uses_existing_layers()` passes
- [ ] `DiscoveryTurnPlan` models moved to `app/intelligence/investigation/plan.py`
- [ ] Discovery Guide still produces identical `TurnResult` output

**Phase 3 complete when:**
- [ ] One `rank_next_actions()` function in `app/intelligence/actions/ranker.py`
- [ ] `ActionRankingContext` accepts context from both Discovery and Personal Evidence
- [ ] At least one Personal Evidence module wired to `rank_next_actions()`
- [ ] All Discovery and PE tests pass with the unified ranker

**Phase 4 complete when:**
- [ ] All 5 internal API endpoints respond correctly with governed output
- [ ] Non-PHI telemetry on all endpoints
- [ ] Auth and owner scoping enforced on all endpoints
- [ ] Rate limiting configured
- [ ] API contracts documented with request/response examples
- [ ] No PHI in endpoint request/response bodies (only stable IDs)

---

## 12. Relationship to existing documentation

| Document | Relationship |
|---|---|
| `PLATFORM_ARCHITECTURE.md` | This document extends PLATFORM_ARCHITECTURE.md. It adds the `app/intelligence/` package to the domain boundary section and updates the Phase 4 API architecture to include intelligence endpoints. |
| `ADR-MVP-007` | Preserved exactly. The Identity Engine is the formalization of ADR-MVP-007. The overlay extensibility mechanism remains the same. |
| `FIVE_SERVICE_FRONTEND_BACKEND_MAP.md` | The five PE services (Regimen, Signals, Experiments, What I Learned, Passport) are the consumers. This document defines the shared infrastructure they all depend on. |
| `REGIMEN_TRUTH_IMPLEMENTATION_REPORT.md` | The Regimen Truth frontend slice is the first UI built against the new IA. This document defines the backend contracts it will eventually wire to. |

---

## Summary

The HerbaGraph Reasoning Core is not a new invention. It is a formalization and extraction of work already present in `app/discovery/`. The composition graph, coverage catalog, evidence transfer invariants, investigation plan models, and next-action ranker are already built. The refactor makes them first-class shared infrastructure that both Discovery and Personal Evidence consume as platform services.

The four-phase plan minimizes risk: each phase produces a working system before the next begins. Discovery never breaks. Personal Evidence modules upgrade their backend contracts one engine at a time.

The strategic outcome is a platform that is dramatically more defensible than "a chatbot about supplements." Enterprise customers can consume governed Identity, Measurement, Evidence, and Action APIs without adopting the consumer UI. The consumer UI (Ask and Personal Evidence) benefits from the same shared intelligence. The two loops — Investigation Loop and Personal Evidence Loop — are now powered by the same reasoning core.
