# HerbaGraph — Product & Technical Overview for Integration Partners

**Audience:** An advanced LLM / platform partner evaluating how HerbaGraph works, what it already does well, and how a custom engine should be integrated into a clinical or biomedical reasoning platform.

**Purpose of this document:** Give enough product, pipeline, data, liability, and architecture context that you can propose **concrete product direction** (what to build next, what to expose as an engine API, what not to reinvent).

**Last calibrated against codebase:** 2026-08 (main branch post marathon PMID growth).

---

## 1. One-sentence product definition

**HerbaGraph is an explainable biological reasoning platform that turns laboratory biomarkers into transparent, evidence-graded, safety-aware intervention insights — organized as a walkable chain from labs → pathways → literature → interventions → confidence & limits — not as a black-box “take this supplement” app.**

---

## 2. Problem it solves

Clinicians, researchers, and sophisticated health users face:

| Pain | Typical market response | HerbaGraph response |
|------|-------------------------|---------------------|
| Lab PDFs / portals are hard to interpret | Flag high/low | Normalize → map biology → explain *why* |
| Supplement advice is uncited or influencer-driven | Product lists | PMID-backed claims + live literature |
| “Inflammation” is vague | Single score | 28 pathways → 7 systems + etiological trees |
| Safety is ignored | Disclaimer only | Graph safety layer (drugs, conditions, organs) |
| LLM hallucination risk | Free-form chat | LLM constrained to retrieved evidence only |
| No audit trail | Screenshots | Provenance, confidence factors, report versions |

**Core thesis:** The value is not “more recommendations.” It is **auditable biological reasoning** that a human decision-maker can inspect, challenge, and take into a clinical conversation.

---

## 3. What HerbaGraph is — and is not

### Is
- Clinical decision **support** / research / education tooling
- Multi-stage **deterministic pipeline** + constrained LLM
- Biomedical **knowledge graph** + curated catalogs + PubMed growth
- Dual knowledge substrates (legacy catalogs vs canonical graph) for A/B
- Multi-patient workspace with auth, reports, tracking, validation feedback

### Is not
- A medical device or diagnostic system
- A prescribing engine (“take 500 mg X”)
- A general medical chatbot
- A replacement for licensed clinical judgment
- A pure black-box ranking model

**Liability design is intentional:** outputs use adjunct framing, require rationale + limitations, surface uncertainty, and carry mandatory disclaimers.

---

## 4. Intended users & jobs-to-be-done

| User | Primary job |
|------|-------------|
| Integrative / functional clinicians | Turn multi-panel labs into discussable, cited intervention classes |
| Researchers / evidence synthesizers | Explore biomarker–pathway–intervention literature structure |
| Sophisticated self-trackers (with clinician) | Understand patterns; prepare questions for visits |
| Platform partners (you) | Embed HerbaGraph’s **reasoning engine** as a module inside a larger medical LLM / clinical OS |

**Not primary (today):** ER triage, acute diagnosis, autonomous treatment, pharmacy fulfillment.

---

## 5. End-to-end product experience

```
Sign up / JWT auth (local or Supabase)
        ↓
Workspace dashboard (patients, labs, reports)
        ↓
Upload lab (PDF / text / CSV / multi-format)
        ↓
Background worker runs 7-stage pipeline
        ↓
Optional knowledge_path: legacy | canonical
        ↓
Interactive report:
  - Abnormal biomarkers + plain-language interpretation
  - Biological systems signal (0–3), not fake “activation %”
  - Ranked interventions by intent & safety
  - Citations (PMID / NCTID), confidence, limitations
  - Food sources for compounds
  - Clinician questions + disclaimer
        ↓
Optional: multi-report trends, response tracking, validation feedback
```

**Marketing / education surfaces:** landing page, How It Works (`/how-it-works.html`), sample report demo.

---

## 6. Design principles (non-negotiable for product direction)

1. **Explain every conclusion** — biomarker → pathway → mechanism → intervention → evidence.
2. **Quantify uncertainty** — confidence levels + factors; never hide gaps.
3. **Separate evidence from opinion** — LLM does not invent PMIDs or free-assert tiers.
4. **Assist, don’t replace** — clinician discussion framing; no directive dosing language.
5. **Typed graph walks over vibes** — recommendations are traversals / catalog claims with provenance, not embeddings-only nearest-neighbor hype.
6. **Safety is a module** — not left solely to the LLM.
7. **Scope honesty** — better a validated core than an unvouchable infinite catalog.

---

## 7. Architecture (system view)

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (static HTML/JS)  — workspace, report, auth UI │
└────────────────────────────┬─────────────────────────────┘
                             │ REST + JWT
┌────────────────────────────▼─────────────────────────────┐
│  FastAPI (app/)  — API, auth, report assembly, KG query  │
└──────────────┬─────────────────────────────┬─────────────┘
               │                             │
        Celery worker                   PostgreSQL (+ pgvector)
        Redis broker                    Encrypted lab files optional
               │
        7-stage pipeline
        + safety_engine
        + evidence_confidence
        + knowledge_graph catalogs / graph edges
               │
        External: PubMed, ClinicalTrials, EuropePMC,
                  PubChem, USDA FoodData, (optional) LLM providers
```

**Deploy pattern:** Railway (API + worker + Postgres); Docker Compose for local. Alembic migrations. GitHub Actions CI gates + cloud PMID growth.

**Auth:** JWT local by default; Supabase OAuth path available; guests off by default (`ALLOW_GUEST_AUTH=false`).

---

## 8. The 7-stage analysis pipeline (product heart)

Every lab analysis is a **pipeline**, not a single LLM call.

| Stage | Module | Input → Output | Product meaning |
|-------|--------|----------------|-----------------|
| **1. Lab parser** | `lab_parser`, provider parsers, optional LLM/OCR fallback | File bytes → `ParsedLabResult[]` | Multi-lab-format intake (Quest, LabCorp, Healow, CSV, pipe, etc.) |
| **2. Biomarker normalizer** | `biomarker_normalizer`, alias resolution, LLM alias assist | Raw names → canonical biomarkers + status | Unifies 100+ aliases into catalog entities |
| **3. Pathway mapper** | `pathway_mapper` | Abnormals → `PathwayActivation[]` | 28 pathways (signaling + etiological), evidence-weighted scores |
| **3b. Test-type router** | `test_type_router` | Labs → recommendation **tree(s)** | H. pylori ≠ CRP ≠ PGx ≠ deficiency |
| **4. Evidence retriever** | `evidence_retriever` + integrations | Pathways/claims → `EvidenceSnippet[]` | Live literature + catalog claims; dedupe by PMID/NCTID |
| **5. LLM reasoner** | `llm_reasoner` | De-identified evidence-only context → structured JSON | Narrative + ranking **from evidence only** |
| **6. Safety layer** | `safety_layer` + `safety_engine` | Candidates + patient context → ratings/warnings | Interactions, contraindications, organ cautions, regulated flags |
| **7. Report generator** | `report_generator` + decision map, tiering, confidence | Final structured report | Tiers, systems rollup, four-lane map, explainability bundle |

### Recommendation trees (test-type routing)

Different abnormals drive different **reasoning trees**, not one global “top supplements” list:

| Tree | Example labs | Typical intent |
|------|--------------|----------------|
| `etiological` | H. pylori DETECTED | Root-cause adjuncts (e.g. mastic, DGL) |
| `signaling` | High CRP, lipids | Host-response modulation |
| `celiac` | tTG IgA+ | Antigen elimination primary |
| `allergy` | Specific IgE | Avoidance + mast-cell context |
| `pgx_context` | CYP genotype | Interaction context **only** — not treatment |
| `nutritional_repletion` | Low B12, D, iron | Deficiency correction |
| (+ others in matrix: autoimmune, infectious expansion, etc.) | | |

**Recommendation intent labels** (critical product concept):

- `primary` — tree-driving
- `collateral` — adjunct
- `context_only` — PGx / exposure / non-directive
- `nutritional_repletion` — measured deficiency

### Biological systems (user-facing)

Internal pathways (16 signaling-style + etiological set = **28** total codes) roll up into **7 systems** with signal 0–3:

1. Inflammation  
2. Metabolic Health  
3. Cardiovascular Risk  
4. Liver Detox/Stress  
5. Nutrient Status  
6. Thyroid/Endocrine  
7. Oxidative Stress / Mitochondrial Resilience  

**Language rule:** “evidence-weighted pathway **signal**,” never “NF-κB is 90% activated.”

---

## 9. Knowledge substrate — dual paths

When generating a report, callers choose:

| Path | Status | Behavior |
|------|--------|----------|
| **`legacy`** | Production default | Curated catalogs + Tier A / longtail / generated PMID claims + live literature retrieval |
| **`canonical`** | Experimental A/B | Traverse typed graph edges on `canonical_entities` (MODULATES / TARGETS / ACTIVATES / INHIBITS / CONTAINS); hybrid-fill from catalogs when sparse |

**Graph anatomy (canonical):**

```
Biomarker + status → Pathway → MODULATES/TARGETS → Intervention
                                      ↓
                              CONTAINS → Food sources of compounds
```

Edge provenance matters:

- **PMID-backed** edges from evidence claims (higher trust)
- **PREDICTED** edges from mechanism heuristics for long-tail coverage (lower trust, labeled)

**Canonical registry layers:** entities (HG IDs), synonyms, external IDs (PubChem, ChEBI, USDA), graph edges, enrichment queue.

---

## 10. Intervention ontology

Everything is an **Intervention** with a category — one ontology, not separate “food app” vs “herb app”:

`food | herb | phytochemical | supplement | exercise | sleep | stress_reduction | medication | peptide | hormone | environmental | behavior`

**Reasoning chain preferred product narrative:**

```
Intervention → Compound → Molecular target → Pathway → Biomarker (clinical proxy)
```

**Food is composition, not the atomic recommendation unit:** reason about **Sulforaphane / Anthocyanins**, then attach `food_sources[]` (richness + serving). That keeps evidence machinery consistent across herbs, nutraceuticals, and diet.

**Regulated classes** (peptides, some hormones, Rx context) are flagged `is_regulated` — never silently sold as lifestyle tips.

---

## 11. Evidence system (how truth is handled)

### Claim sources (layered)

1. **Tier A curated claims** — hand-curated, verifiable PMIDs, recommendation_intent  
2. **Long-tail / lifestyle / peptide catalogs** — specialized claim sets  
3. **Generated PMID claims** — automated NCBI search with **title-match acceptance**; never invents PMIDs  
4. **Live retrieval** — PubMed / ClinicalTrials.gov / Europe PMC at analysis time  
5. **Predicted graph edges** — mechanism-based coverage without pretending to be clinical literature  

### Integrity culture

- `audit_pmid_integrity.py` — denylist, keyword maps, optional strict network check  
- `audit_evidence_gaps.py` — ≥5 routable claims on each of 28 priority pathways  
- Cloud **PMID growth** (GitHub Actions): daily 100–200; marathon mode for large hybrid fills  
- Marathon reality check: after deep fill (~2.3k generated claims), residual queue yields little until `min_claims` increases or catalog expands  

### Evidence confidence engine

Post-reasoning, pre-final ranking: **deterministic** confidence (not LLM-asserted).

- Levels High / Moderate / Low from transparent factor weights  
- Quality hierarchy: meta-analysis > SR > RCT > observational > mechanistic > preclinical…  
- Explainability bundle: why recommended, why not higher, provenance, gaps, contradictory evidence  

### Evidence tiers on report

Derived from studies actually cited — LLM cannot freely assign “strong evidence.”

---

## 12. Safety engine

Independent module (`app/safety_engine/`):

**Inputs:** age, sex, meds, supplements, conditions; optional organ labs (eGFR, LFTs).

**Outputs per intervention:** safety_rating, typed warnings (interaction, contraindication, organ_caution, pregnancy_lactation), prominent-warning flag.

**Graph of safety relationships:** interacts_with, contraindicated_in, use_with_caution, etc.

**Product stance:** inform and demote; keep transparency. Does not silently delete all options without explanation (UI surfaces warnings).

MVP scale: tens of medications, condition categories, seeded edges — expandable as graph nodes, not pipeline rewrites.

---

## 13. Report product surface (what the engine must produce)

A complete report is a **structured clinical reasoning artifact**, typically including:

- Patient/session metadata (de-identified where required)  
- Normalized biomarkers + status + plain-language interpretation  
- Pathway activations + biological_systems signals  
- Primary recommendation tree + decision map (four lanes: direct biomarker, lifestyle, supportive adjunct, regulated context)  
- Ranked recommendations with: category, intent, dose *context if evidence-supported*, mechanism, citations, rationale, limitations, evidence tier, safety, food_sources, explainability  
- Questions for a clinician  
- Methodology / versioning / knowledge_path  
- Mandatory disclaimer  

**Demo path:** sample clinical report JSON + `report.html?demo=1`.

---

## 14. Current scale (approx., evolving)

| Asset | Approximate scale |
|-------|-------------------|
| Catalog interventions (merged catalogs) | ~800–900 names |
| Pathway codes | **28** |
| User-facing biological systems | **7** |
| Recommendation trees | **9** |
| Tier A + extended claim pool | **~2.6k+** claims post growth (includes ~2.3k generated PMID rows) |
| Lab scenario matrix | **~80** CI scenarios + adversarial resilience probes |
| Biomarker MVP framing (README) | Core panel ~25 tracked “MVP” biomarkers; normalizer covers broader aliases |
| Graph edges (after bootstrap) | Thousands of MODULATES/TARGETS/CONTAINS (env-dependent) |
| Safety meds / edges | ~44 meds, 10 condition categories, 30+ edges (MVP) |

*Numbers move with reseed, bootstrap, and PMID marathons — product direction should treat catalogs as living.*

---

## 15. Tech stack (integration-relevant)

| Layer | Choice |
|-------|--------|
| API | Python 3.11+/3.12, FastAPI, Pydantic |
| Async DB | SQLAlchemy async, PostgreSQL |
| Jobs | Celery + Redis |
| Migrations | Alembic |
| LLM | OpenAI-compatible + optional fallback providers (config-driven) |
| Auth | JWT local; Supabase OAuth path |
| Frontend | Static HTML/JS (no heavy SPA framework required) |
| CI | Ruff + multi-gate scripts + large pytest suite |
| Cloud ops | Railway, GitHub Actions PMID growth |

---

## 16. API / engine integration surface (what a partner would call)

High-level capability groups under `/api/v1/`:

| Domain | Examples |
|--------|----------|
| Auth | signup, login, me, password reset |
| Patients / context | multi-patient, meds/conditions context |
| Labs | upload, parse status, multi-report merge |
| Analysis sessions | run pipeline with `knowledge_path` |
| Reports | generate, fetch structured report, regenerate |
| Evidence | list interventions, claims, food sources |
| Knowledge | canonical entities, enrichment (admin) |
| Safety | meds, conditions, evaluate profiles |
| Explainability | evaluate / fetch bundles |
| Workspace | dashboard aggregates |
| Validation | clinician/product feedback loops |
| Tracking | response / outcome tracking hooks |

**Critical request field for A/B:** `knowledge_path: "legacy" | "canonical"`.

**Auth for engine embedding:** service-to-service JWT or partner-scoped keys would be a *product decision* (not fully productized as multi-tenant B2B yet — assume user/patient scoped API today).

---

## 17. Privacy & de-identification

- Lab text de-identified before LLM calls  
- Optional encrypted file storage for lab blobs  
- Prefer not to send full PHI to third-party models  
- Audit events for sensitive operations  

Any partner integration must preserve: **de-id before external LLM**, **auditability**, **no training on customer PHI by default**.

---

## 18. Differentiation vs adjacent products

| Category | Typical product | HerbaGraph difference |
|----------|-----------------|------------------------|
| Lab viewer apps | Pretty charts of highs/lows | Pathway + tree routing + interventions |
| Supplement quiz apps | Lifestyle questionnaire → SKUs | Lab-grounded, cited, safety-checked |
| Generic medical LLMs | Free-form answers | Evidence-bounded pipeline + graph |
| Pure KG startups | Graph without UX | End-to-end report + dual path + safety |
| CDS for Rx only | Drug guidelines | Integrative ontology (food/herb/lifestyle/peptide) with regulated flags |

**Moat candidates:** (1) test-type trees + etiological vs signaling split, (2) dual knowledge path A/B, (3) confidence/explainability not LLM-asserted, (4) continuous real-PMID growth with integrity gates, (5) food-as-compound composition layer.

---

## 19. Milestone map (product maturity)

| Milestone | Meaning | Status |
|-----------|---------|--------|
| **M1** Reliable legacy | Abnormal catalog biomarker → pathway → claims → recs | Largely done |
| **M2** Catalog depth | PMID density on high-traffic + long-tail | Advanced (generated marathons + predicted edges) |
| **M3** Graph-backed recs | Canonical MODULATES/TARGETS engine + hybrid fill | Integrated (experimental path) |
| **M4** Clinical completeness | All trees balanced, multi-panel, food/safety attach polished | Ongoing |

---

## 20. What a “custom engine integration” likely means (for the partner LLM)

When the founder says they will **integrate a custom engine into another advanced medical LLM platform**, interpret HerbaGraph as providing one or more of:

### A. Reasoning Engine API (recommended core productize)
Partner sends: de-identified labs (+ optional meds/conditions) + path choice.  
HerbaGraph returns: full structured reasoning report JSON (systems, trees, recs, confidence, safety, citations).

### B. Knowledge Graph / Evidence Substrate only
Partner keeps their UX/LLM; calls HerbaGraph for: pathway map, claim retrieval, food sources, safety profile, explainability scoring.

### C. Pipeline-as-a-service stages
Composable: parse-only, normalize-only, retrieve-only, safety-only — for embedding inside partner orchestration.

### D. Dual-path research bench
Partner runs `legacy` vs `canonical` side-by-side for evaluation, adjudication, and model training labels (with care — claims are research artifacts, not ground truth diagnoses).

**What HerbaGraph should not become for the partner:** ungrounded chat that rephrases the partner LLM’s guesses with fake PMIDs.

---

## 21. Strong product directions (for the partner to refine)

Use these as starting hypotheses; prioritize with founder goals.

### Engine productization
1. **Versioned Engine API** (`/v1/engine/analyze`) with stable JSON schema, SLA, knowledge_path, model_version.  
2. **Strict schema contract** for recommendations (intent, tier, pmid list, safety_rating, confidence_factors).  
3. **Idempotent analysis sessions** for multi-panel merge (already partly present).  
4. **Partner auth**: org keys, rate limits, audit per tenant.

### Clinical depth
5. **Tree balance M4** — every tree has golden scenarios + min claim density.  
6. **Contradiction engine** — surface opposing literature more explicitly.  
7. **Longitudinal** — trend context and intervention response tracking as first-class partner features.  
8. **Panel completeness** — “highest value missing labs” already a capability theme; productize as diagnostic optimization module.

### Knowledge quality
9. **Human review queue** for generated PMIDs (auto-grow is scale; clinicians want grade).  
10. **min_claims depth campaigns** after claimless saturation.  
11. **Canonical path promotion criteria** — when does graph path become default?  
12. **USDA/PubChem enrichment** as partner-visible provenance on compounds/foods.

### Safety & liability
13. Expand safety graph coverage (top 200 meds, pregnancy, peds flags).  
14. Jurisdiction-aware disclaimers; exportable “show your work” PDF for charts.  
15. Never auto-prescribe peptides/hormones; keep regulated lane.

### UX for partner embedding
16. Embeddable **decision map** + **reasoning graph** widgets (frontend already has reasoning-graph concepts).  
17. How-it-works style methodology panel as trust UI for end clinicians.  
18. Knowledge path picker as research control, not patient confusion — default legacy.

### What to avoid
- Inflating catalog with unverifiable claims for vanity counts  
- Letting partner LLM rewrite PMIDs  
- Collapsing etiological and signaling trees into one “wellness score”  
- Selling activation % or disease diagnosis labels  

---

## 22. Open product questions for the partner conversation

1. Is the partner’s user a **clinician**, **patient**, or **both** — and who is the liability bearer?  
2. Does the partner need **full reports** or **atomic engine modules**?  
3. Must outputs be **on-prem / VPC**, or is multi-tenant SaaS acceptable?  
4. How strict is **citation policy** (PMID required vs mechanism-only allowed)?  
5. Should `canonical` graph be co-developed as the long-term substrate?  
6. What is the partner’s existing **safety / formulary** system — merge or replace?  
7. Is multi-lab longitudinal required on day one?  
8. Which lab ecosystems matter (Quest, LabCorp, EHR PDFs, FHIR)?  
9. Will the partner’s LLM remain the **narrator** while HerbaGraph is the **reasoner**, or inverse?  
10. What success metric: clinical time saved, citation density, user retention, adjudication agreement?

---

## 23. Suggested prompt the founder can give the partner LLM

> You are advising product direction for integrating **HerbaGraph** as a custom biological reasoning engine into our advanced medical LLM platform.  
>  
> HerbaGraph is an explainable, multi-stage biomarker → pathway → evidence → intervention pipeline with dual knowledge paths (legacy catalogs vs canonical graph), deterministic confidence scoring, a safety graph, test-type recommendation trees (etiological vs signaling vs PGx vs nutritional), and strict “no invented PMIDs” evidence policy. It is **not** a diagnostic medical device.  
>  
> Read the full overview (this document). Then produce:  
> 1) A recommended **integration architecture** (what we call, what we own).  
> 2) A **phased roadmap** (MVP embed → clinical trust → scale).  
> 3) **API contract sketch** for the engine.  
> 4) Risks (liability, hallucination, safety, data).  
> 5) Differentiation strategy for our platform.  
> 6) Explicit non-goals.  
> Prefer concrete modules and interfaces over vague AI strategy language.

---

## 24. Key repository map (for engineers)

| Path | Role |
|------|------|
| `app/pipeline/` | 7-stage analysis pipeline |
| `app/knowledge_graph/` | Catalogs, claims, registry, graph seed |
| `app/safety_engine/` | Safety graph evaluation |
| `app/evidence_confidence/` | Confidence + explainability |
| `app/api/v1/` | HTTP surface |
| `app/workers/` | Celery tasks |
| `frontend/` | Workspace, report, how-it-works |
| `samples/lab_scenarios/` | Scenario matrix for CI |
| `scripts/ci_gates.sh` | Definition of done |
| `docs/EVIDENCE_CONFIDENCE_ENGINE.md` | Confidence deep dive |
| `docs/SAFETY_ENGINE.md` | Safety deep dive |
| `README.md` | Primary product/engineering doc |
| `.github/workflows/pmid-growth.yml` | Continuous real-PMID growth |

---

## 25. Closing framing for product direction

HerbaGraph’s strategic asset is **structured, inspectable biological reasoning** — the combination of:

- multi-format lab understanding,  
- tree-routed clinical logic,  
- dual knowledge substrates,  
- real literature with integrity culture,  
- safety and confidence modules that do not trust the LLM alone.

The right partner integration is not “wrap chat around our graph.” It is **expose the pipeline as a versioned clinical reasoning engine** with stable contracts, while the partner LLM provides conversation, orchestration, and UI — without being allowed to invent the evidence layer.

---

*Document generated for partner/LLM product strategy. Not medical advice. Counts and module paths evolve with the repository.*
