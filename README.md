# HerbaGraph

**An Explainable Biological Reasoning Platform for Biomarker Interpretation and Evidence-Based Integrative Medicine.**

HerbaGraph is an AI-powered biomedical reasoning platform that transforms laboratory biomarkers into transparent, evidence-based biological insights.

Rather than simply flagging abnormal lab values or recommending supplements, HerbaGraph constructs an explainable chain of reasoning that connects laboratory biomarkers to biological systems, molecular pathways, scientific evidence, safety considerations, and potential evidence-supported intervention classes.

The platform combines a biomedical knowledge graph, explainable AI, structured scientific evidence, and clinical reasoning to help researchers and clinicians better understand the biological significance of laboratory findings while clearly communicating confidence, uncertainty, and research limitations.

## Core Capabilities

- Multi-report laboratory aggregation into a unified patient profile
- Biomarker normalization and interpretation
- Biological systems and pathway mapping
- Explainable biological reasoning
- Evidence grading using human clinical literature
- Differential biological explanations
- Evidence confidence and uncertainty estimation
- Diagnostic optimization through identification of high-value missing biomarkers
- Safety-aware evidence synthesis
- Transparent evidence provenance and literature citation
- Knowledge graph–driven intervention discovery across botanicals, nutraceuticals, foods, peptides, lifestyle interventions, and emerging therapeutic classes

## Design Philosophy

HerbaGraph is designed around four guiding principles:

1. Explain every conclusion.
2. Quantify uncertainty rather than hide it.
3. Separate evidence from opinion.
4. Assist human decision-making rather than replace it.

Rather than functioning as a recommendation engine, HerbaGraph acts as an explainable biological reasoning platform that organizes complex biomedical knowledge into transparent, auditable, and clinically interpretable reports.

The platform is intended for research, evidence synthesis, educational use, and future clinical decision support development. It is not intended to diagnose disease or replace professional medical judgment.

---

## ⚠️ Important Disclaimer

**HerbaGraph is a clinical decision support and research tool, not a medical device.** All outputs are for educational and research purposes only. They do not constitute medical advice, diagnosis, or treatment. Every recommendation is evidence-graded and framed to support a discussion with a qualified healthcare provider — never as a directive to take or do something on its own. Always consult a qualified healthcare provider before starting, modifying, or stopping any supplement, medication, or lifestyle intervention.

---

## Table of Contents

- [Core Capabilities](#core-capabilities)
- [Design Philosophy](#design-philosophy)
- [Architecture](#architecture)
- [MVP Scope](#mvp-scope)
- [Pipeline Overview](#pipeline-overview)
- [Recommendation Trees & Etiological Pathways](#recommendation-trees--etiological-pathways)
- [Biological Systems & Signal Scoring](#biological-systems--signal-scoring)
- [Intervention Ontology](#intervention-ontology)
- [Knowledge Paths (Legacy vs Canonical)](#knowledge-paths-legacy-vs-canonical)
- [Food → Compound Layer](#food--compound-layer)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Privacy Design](#privacy-design)
- [Evidence Grading](#evidence-grading)
- [Confidence Scoring](#confidence-scoring)
- [Running Tests](#running-tests)
- [Development Guide](#development-guide)
- [Knowledge Graph](#knowledge-graph)
- [Safety Layer](#safety-layer)
- [Auth & Multi-Patient Mode](#auth--multi-patient-mode)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      HerbaGraph API                      │
│                      (FastAPI + JWT)                     │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /labs/upload
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Celery Worker                          │
│                (Redis message broker)                    │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  7-Stage Pipeline │
              └────────┬────────┘
                       │
       ┌───────────────▼───────────────────────────────┐
       │                                               │
  1. Lab Parser          ──► ParsedLabResult[]         │
  2. Biomarker Normalizer ──► NormalizedLabResult[]     │
  3. Pathway Mapper       ──► PathwayActivation[]       │
  4. Evidence Retriever   ──► EvidenceSnippet[]         │
       │  (PubMed + ClinicalTrials + EuropePMC)        │
  5. LLM Reasoner         ──► LLMReasoningOutput        │
       │  (OpenAI gpt-4o, de-identified)               │
  6. Safety Layer         ──► SafetyReport              │
  7. Report Generator     ──► FinalReport               │
       │                                               │
       └─────────────────────────────────────────────-─┘
                       │
              ┌────────▼────────┐
              │   PostgreSQL +   │
              │    pgvector      │
              └─────────────────┘
```

---

## MVP Scope

HerbaGraph deliberately caps its scope rather than trying to cover every biomarker, pathway, or intervention that exists -- a narrower, well-validated MVP is more useful (and more honest) than a broad one nobody can vouch for.

- **25 biomarkers max** (a 17-test core panel + 8 optional near-MVP additions), not 100+. See [Knowledge Graph](#knowledge-graph) for the full list.
- **16 pathways internally, but only 7 systems shown to the user.** Mapping biology to 16 named pathways is fine as an internal representation; showing a patient 16 pathway codes is not actionable. See [Biological Systems & Signal Scoring](#biological-systems--signal-scoring).
- **A simple 0-3 signal scale**, not a false-precision decimal. Internally each pathway still gets a continuous 0-1 evidence-weighted score (used for confidence-scoring math), but everything user-facing is bucketed into No/Mild/Moderate/Strong Signal.
- **Evidence-weighted signal, never "activation."** The pipeline has not measured biological activation directly -- only inferred a signal from lab values and published mechanism-of-action literature. Output is phrased "Inflammation Signal: Elevated, Confidence: Moderate, Drivers: CRP" -- never "NF-κB is 90% activated."

---

## Pipeline Overview

### Stage 1: Lab Parser
Accepts PDF (via OCR) or plain text lab reports. Supports Quest, LabCorp, and most standard tabular formats using four layered regex patterns. Falls back to pytesseract OCR for scanned PDFs.

### Stage 2: Biomarker Normalizer
Maps 100+ raw lab test names (aliases, abbreviations, manufacturer variations) to a canonical set of 25 biomarkers (see [MVP Scope](#mvp-scope)). Classifies each result as `critical_low`, `low`, `optimal`, `normal`, `high`, or `critical_high` using both lab-provided and clinically-validated reference ranges.

### Stage 3: Pathway Mapper
Maps each abnormal biomarker to **28 pathways** — 16 host **signaling** pathways (NF-κB, AMPK, Nrf2, etc.) plus 12 **etiological** pathways (gastric colonization, food antigen exposure, IgE sensitization, etc.). 90+ biomarker-to-pathway rules. The 16 signaling pathways roll up into 7 user-facing biological systems; etiological pathways drive root-cause recommendation trees separately.

### Stage 3b: Test-Type Router (`app/pipeline/test_type_router.py`)
Before evidence retrieval, each abnormal lab is classified by `result_kind` + biomarker `category` into one or more **recommendation trees**:

| Tree | Example labs | What surfaces |
|---|---|---|
| `etiological` | H. pylori breath test DETECTED | Mastic Gum, DGL Licorice (primary) |
| `signaling` | High CRP, high LDL | Curcumin, Omega-3, Berberine |
| `celiac` | tTG IgA positive | Gluten Elimination Diet (primary) |
| `allergy` | Peanut IgE elevated | Avoidance context + mast-cell adjuncts |
| `pgx_context` | CYP2D6 genotype | Interaction context only — not treatment recs |
| `nutritional_repletion` | Low B12, low Vitamin D | B12, Vitamin D, Iron |

The router picks a **primary tree** that controls intervention ranking and narrative framing.

### Stage 4: Evidence Retriever
Builds intervention-specific PubMed queries from **routed pathways + biomarker-direct evidence claims** (not a single global NF-κB list). Concurrently fetches from PubMed, ClinicalTrials.gov, and Europe PMC. Deduplicates by PMID/NCTID and ranks by study quality.

### Stage 5: LLM Reasoning
Sends a de-identified payload to an OpenAI model (gpt-4o by default). The LLM reasons **only** from retrieved evidence snippets — it cannot free-invent claims. The system prompt is written to reduce liability by design: it forbids directive language ("take 500mg"), requires every recommendation to state *why it was surfaced* (`rationale`) and *what the evidence doesn't show* (`limitations`), and instructs the model to frame everything as input to a discussion with a clinician, never as a decision made on the reader's behalf. Returns a structured JSON with: biomarker pattern analysis, pathway summaries, ranked recommendations with dose/mechanism/citations/rationale/limitations, and questions to ask a clinician.

### Stage 6: Safety Layer
Runs every recommendation through an explicit staged pipeline, in order:
1. **Drug interaction check** — drug-herb interaction database (warfarin, metformin, SSRIs, cyclosporine, and more)
2. **Contraindication check** — pregnancy, severe kidney disease, autoimmune conditions on immunosuppressants; matched recommendations are removed from the final report entirely
3. **Pregnancy check** — evaluated first/independently within the contraindication check
4. **Kidney/Liver warning** — a softer flag (not an exclusion) for interventions with a liver-safety signal when the patient's profile indicates liver disease
5. **Regulated-intervention flagging** — BPC-157, peptides, GLP-1 agonists, etc. are labeled `is_regulated: true`, never silently recommended

### Stage 7: Report Generator
Applies a composite confidence scoring formula, derives each recommendation's **evidence tier** deterministically from the studies actually cited (never asserted by the LLM), generates a plain-language interpretation per abnormal biomarker, rolls the 16 internal pathways up into 7 biological systems (see below), ranks surviving recommendations, and assembles the final structured report with citations, safety summary, clinician questions, and a mandatory disclaimer.

---

## Biological Systems & Signal Scoring

Internally, `app/pipeline/pathway_mapper.py` maps abnormal biomarkers to 16 named pathways with a continuous 0-1 evidence-weighted score (used in the confidence-scoring math). But showing a patient 16 pathway codes isn't actionable, so `app/pipeline/biological_systems.py` rolls those 16 pathways up into **7 stable, user-facing systems** and reduces the score to a simple 0-3 scale:

| System | Rolls up these internal pathways |
|---|---|
| Inflammation | NF-κB, IL-6/JAK-STAT3 |
| Metabolic Health | Insulin/PI3K-Akt, GLP-1/Incretins, AMPK |
| Cardiovascular Risk | Hepatic Lipid, Purine/Uric Acid, Renal Filtration |
| Liver Detox/Stress | Hepatic Lipid, Nrf2 |
| Nutrient Status | One-Carbon/Methylation, Iron/Hepcidin, Vitamin D Receptor |
| Thyroid/Endocrine | Thyroid/HPT, HPA Axis |
| Oxidative Stress / Mitochondrial Resilience | Nrf2, mTOR/Autophagy, Mitochondrial NAD+ |

A pathway can inform more than one system where clinically justified (e.g. Hepatic Lipid matters for both cardiovascular risk and liver stress) -- systems are lenses on the same 16 pathways, not a disjoint partition.

**Signal score (0-3)**, computed from: biomarker abnormality strength (the pathway's evidence-weighted score) + number of supporting biomarkers, per `app/pipeline/biological_systems.py::_signal_level`:

| Level | Label |
|---|---|
| 0 | No Signal |
| 1 | Mild Signal |
| 2 | Moderate Signal |
| 3 | Strong Signal |

Example output shape (this is what `biological_systems` looks like in a `GET /reports/{id}` response):
```json
{
  "system_code": "inflammation",
  "system_name": "Inflammation",
  "signal_level": 2,
  "signal_label": "Moderate Signal",
  "direction": "elevated",
  "confidence": "moderate",
  "drivers": ["CRP"],
  "pathways": [{"pathway_code": "NF_KB", "pathway_name": "NF-κB Inflammatory Signaling"}]
}
```

Wording is deliberate: **"evidence-weighted pathway signal," never "activation score."** HerbaGraph has not measured biological activation directly -- it has inferred a signal from a lab value and published mechanism-of-action literature. `pathway_activations` (the detailed pathway breakdown, including etiological pathways) is still included in the report response for anyone who wants the detail, but `biological_systems` is the recommended thing to render.

---

## Recommendation Trees & Etiological Pathways

Different lab tests need different reasoning chains. A positive H. pylori breath test should not route through the same intervention list as an elevated CRP.

```
Abnormal lab → Test-Type Router → Recommendation Tree(s)
                                      ↓
              ┌───────────────────────┴────────────────────────┐
              │                                                │
     Etiological pathways                          Signaling pathways
     (root cause)                                  (host response)
              │                                                │
     Biomarker-direct claims                         Pathway → intervention map
     (H. pylori → Mastic Gum)                        (CRP → Curcumin)
              └───────────────────────┬────────────────────────┘
                                      ↓
                           Evidence retrieval + LLM reasoning
                                      ↓
                    Narrative with recommendation_intent label
                    (primary / collateral / context_only / nutritional_repletion)
```

### Etiological pathway codes (12)

| Code | Use case |
|---|---|
| `GASTRIC_COLONIZATION` | H. pylori breath/stool antigen |
| `GI_MUCOSAL_BARRIER` | Mucosal healing adjuncts |
| `PATHOGEN_BURDEN` | Active infection markers |
| `FOOD_ANTIGEN_EXPOSURE` | Celiac serology (tTG, EMA, DGP) |
| `IGE_SENSITIZATION` | Allergen-specific IgE |
| `NUTRIENT_DEFICIENCY` | Low B12, Vitamin D, Ferritin, etc. |
| `DRUG_METABOLISM_VARIANT` | Pharmacogenomics (context only) |
| ... | See `ETIOLOGICAL_PATHWAYS` in `app/knowledge_graph/seed_data.py` |

### Tier A curated catalog (quality over count)

The knowledge graph no longer pads to 200 placeholder herbs. All production interventions live in:

- `app/knowledge_graph/tier_a_catalog.py` — 76 evidence-backed entries (16 herbs, 19 supplements/lifestyle, 15 foods, 16 phytochemicals) + 10 clinical peptides
- `app/knowledge_graph/tier_a_evidence.py` — 49 claims, each with a **verifiable PMID** and `recommendation_intent`

Grow toward 200 **only** by adding entries with real compounds, targets, and literature — not template generation.

### Reseed after catalog changes

```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/reseed_db.py
docker compose restart api worker
```

---

## Intervention Ontology

HerbaGraph doesn't model "herbs" and "foods" and "exercise" as separate systems — everything the graph reasons about is an **Intervention**, distinguished only by `category`:

| Category | Examples |
|---|---|
| `food` | Broccoli Sprouts, Garlic, Cooked Tomatoes |
| `herb` | Boswellia serrata, Mastic Gum, DGL Licorice, Ashwagandha, Milk Thistle |
| `phytochemical` | Sulforaphane, Curcumin, Anthocyanins, EGCG, Quercetin |
| `supplement` | Berberine, Omega-3, Magnesium, Vitamin D, CoQ10 |
| `exercise` | HIIT |
| `sleep` | Sleep Hygiene Optimization |
| `stress_reduction` | Mindfulness-Based Stress Reduction |
| `medication` | (regulated; surfaced for evidence context only) |
| `peptide` | BPC-157, TB-500 (regulated) |
| `hormone` | GLP-1/GIP receptor agonists (regulated) |
| `environmental` | — |
| `behavior` | Intermittent Fasting |

None of these is treated as inherently more "medical" than another — they differ only in their evidence base and safety profile, both of which the pipeline evaluates identically regardless of category.

### The full graph

```
Intervention  →  Compound  →  Target  →  Pathway  →  Biomarker  →  Clinical Outcome
```

- **Intervention → Compound**: a herb/food/supplement's chemical constituents (`app/models/compound.py`'s `InterventionCompound` join). E.g. Boswellia serrata → AKBA.
- **Compound → Target**: each `Compound.primary_target` is the molecular target it acts on (a receptor, enzyme, or transcription factor) — e.g. AKBA → 5-LOX, Curcumin → NF-κB, Berberine → AMPK. `pubchem_cid` is intentionally left unset in static seed data — it's resolved on demand via `app/integrations/pubchem.py` rather than hardcoded, so it can't silently go stale.
- **Target → Pathway → Biomarker**: comes from the parent intervention's own `EvidenceClaim`s, since the retrieved clinical evidence is almost always about the whole herb/food, not an isolated constituent studied alone.
- **→ Clinical Outcome**: the abnormal biomarker itself is the proxy for the clinical outcome being reasoned about (e.g. ↓CRP as a proxy for reduced systemic inflammation).

This is why the reasoning layer never says "eat blueberries" — it reasons about the compound (Anthocyanins), which carries the same Target/Pathway/Biomarker/evidence machinery as any herb, and then attaches `food_sources` so the food is just one of several ways to obtain it (see below).

### Canonical intervention registry (Level 1–5)

Alongside the curated catalogs, HerbaGraph now has a **canonical entity registry** (`canonical_entities`, synonyms, external IDs, graph edges, enrichment queue):

| Layer | Purpose |
|---|---|
| Canonical entities | HG IDs (`HG-FOOD-…`, `HG-BOT-…`, `HG-CMP-…`) for foods, botanicals, compounds, lifestyle, peptides |
| Synonyms | Normalized alias resolution |
| External IDs | PubChem, ChEBI, USDA FDC, intervention/compound UUIDs |
| Graph edges | Composition `CONTAINS` (and future MODULATES/TARGETS) |
| Enrichment queue | Machine expansion with external ID + synonym deep enrichment |

**Bootstrap (after reseed):**

```bash
python scripts/reseed_db.py
python scripts/bootstrap_canonical_registry.py
# or one-shot on Railway:
bash scripts/railway_bootstrap.sh
```

**Deep enrichment:**

```bash
python scripts/verify_usda_key.py          # local or: railway run python scripts/verify_usda_key.py
python scripts/deep_enrichment_pass.py    # enqueue missing IDs + process queue batch
```

---

## Knowledge Paths (Legacy vs Canonical)

When you **generate or regenerate a report**, the workspace asks which knowledge substrate to use:

| Path | Value | Behavior |
|---|---|---|
| **Legacy catalogs** | `legacy` | Production default. Curated intervention catalogs + Tier A evidence claims + live literature retrieval. |
| **Canonical graph** | `canonical` | Experimental A/B. Filters routed interventions to entities present in `canonical_entities` (run bootstrap first). Tags the report with `knowledge_path` + meta stats. |

**API:**

```http
POST /api/v1/reports/generate/{lab_report_id}
Authorization: Bearer {token}
Content-Type: application/json

{ "knowledge_path": "canonical" }
```

```http
POST /api/v1/analysis-sessions/{session_id}/run
Content-Type: application/json

{ "knowledge_path": "legacy" }
```

Reports persist `knowledge_path` and expose it on `GET /reports/{id}` (also reflected in `model_version` as `1.0.0-legacy` / `1.0.0-canonical`). The UI picker is `frontend/js/knowledge-path-picker.js`.

### Recommendation depth milestones

| Milestone | Status | Meaning |
|-----------|--------|---------|
| **M1** Reliable legacy | Done | Abnormal catalog biomarker → pathway → claims → recs in scenarios/UI |
| **M2** Full catalog depth | Advanced | PMID claims for high-traffic catalog; long-tail via predicted graph edges |
| **M3** Graph-backed recs | Integrated | Full MODULATES/TARGETS engine on `knowledge_path=canonical` (hybrid fill) |
| **M4** Clinical completeness | Ongoing | All 9 trees balanced; multi-panel scenarios; food/safety attach |

**Graph recommendation engine** (`knowledge_path=canonical`):

1. Register pathway nodes (`HG-PATH-*`) and intervention nodes  
2. Seed edges from evidence claims (PMID-backed) + catalog mechanism heuristics (PREDICTED for ~700 claim-less items)  
3. Traverse pathway activations → MODULATES → ranked interventions  
4. Attach graph CONTAINS food sources; hybrid-fill with legacy when sparse  

```bash
python scripts/bootstrap_canonical_registry.py
python scripts/bootstrap_graph_edges.py
```

**How it works UI:** `/how-it-works.html` — step-by-step pipeline walkthrough with charts.

**IMP-053** LLM alias assist runs after parse when deterministic aliases miss (mock heuristics in CI).

**IMP-002 registered sessions:** Guest accounts are **off by default** (`ALLOW_GUEST_AUTH=false`). Local auth persists **JWT only** (never the password). Sign up or sign in to keep labs/reports.

**Evidence gates:** `scripts/audit_evidence_gaps.py` requires **≥5** routable claims on each of 28 priority pathways.

### Growing real PMID claims continuously

Use the project skill **`/herbagraph-pmid-growth`**:

```bash
# See next claim-less interventions
python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py --limit 20

# In Grok: run /herbagraph-pmid-growth  (adds 10–15 real PMIDs, runs integrity gates)
# Optional daily durable schedule: ask the agent to scheduler_create interval=1d with that prompt
```

---

## Food → Compound Layer

Most nutrition apps organize around **products**: calories, macros, "eat this food." HerbaGraph organizes around **biology** instead — food is just another intervention type in the same graph as herbs, supplements, and other levers.

```
Food                          Compound (phytochemical)         Pathway / Biomarker
────                          ─────────────────────────        ───────────────────
Broccoli Sprouts  ──high──┐
Broccoli          ──mod───┼──► Sulforaphane ──────────────────► Nrf2 activation ──► ↓ CRP, ↓ oxidative stress
Brussels Sprouts  ──mod───┤
Kale              ──low───┘

Garlic            ──high──────► Allicin ────────────────────────► NF-κB inhibition ──► ↓ LDL

Blueberries       ──high──┐
Blackberries      ──high──┼───► Anthocyanins ───────────────────► Nrf2 / endothelial ──► ↓ CRP, ↓ LDL
Purple Grapes     ──mod───┘
```

### Why compounds, not products

The reasoning layer (Layer 2) never recommends "eat blueberries." It recommends **the compound the evidence actually supports** — e.g. *Anthocyanins*, backed by the same citation/evidence-tier/safety-flag machinery as any herb or nutraceutical. The report then attaches a **food_sources** list so the person can pick whichever source fits their diet:

```json
{
  "intervention_name": "Sulforaphane",
  "category": "phytochemical",
  "evidence_tier_label": "Emerging Evidence",
  "food_sources": [
    {"food": "Broccoli Sprouts", "richness": "high", "typical_serving": "1/4 cup fresh sprouts"},
    {"food": "Broccoli", "richness": "moderate", "typical_serving": "1 cup steamed"},
    {"food": "Brussels Sprouts", "richness": "moderate", "typical_serving": "1 cup cooked"},
    {"food": "Kale", "richness": "low", "typical_serving": "1-2 cups raw"}
  ]
}
```

Someone who doesn't like broccoli can choose Brussels sprouts. Someone who avoids one berry can pick another rich in anthocyanins. The recommendation stays grounded in the evidence; only the delivery vehicle changes.

### Data model

- **`Intervention`** includes `food` and `phytochemical` among its `InterventionCategory` values (see [Intervention Ontology](#intervention-ontology) for the full set). A phytochemical compound (e.g. Sulforaphane) is a first-class Intervention row with its own `mechanism`, `EvidenceClaim`s, `SafetyFlag`s, and `DrugInteraction`s — identical treatment to any herb.
- **`FoodCompoundSource`** is the many-to-many join: `food_intervention_id` ↔ `compound_intervention_id`, with a `richness` (`high` \| `moderate` \| `low`), `typical_serving`, and an optional bioavailability note (e.g. "cooking with oil increases lycopene absorption"). This is a *food-specific* join distinct from `InterventionCompound` (which links a herb/supplement to its chemical *constituents* — see [Intervention Ontology](#intervention-ontology)); both exist because "Anthocyanins in blueberries" and "AKBA in Boswellia" are conceptually different relationships (a food is a dietary *source* of a compound; a herb extract *contains* a compound as an active constituent).
- A **static, zero-latency lookup dict** (`COMPOUND_TO_FOOD_SOURCES` in `app/knowledge_graph/food_seed_data.py`) mirrors the DB table so the pipeline can attach `food_sources` to a recommendation without a database round-trip — the same pattern already used for pathway→intervention mapping.

### Seeded compounds

| Compound | Primary mechanism | Food sources |
|---|---|---|
| Sulforaphane | Nrf2 activation | Broccoli sprouts, broccoli, Brussels sprouts, kale |
| Anthocyanins | Nrf2 / endothelial function | Blueberries, blackberries, purple grapes |
| EGCG | AMPK activation, NF-κB inhibition | Green tea |
| Allicin | HMG-CoA reductase inhibition | Garlic |
| Ellagic Acid | Nrf2 activation (via urolithins) | Pomegranate |
| Lycopene | LDL-oxidation inhibition | Cooked tomatoes |
| Beta-Carotene | Nrf2 activation, provitamin A | Carrots |
| Quercetin | NF-κB / xanthine oxidase inhibition | Onions |

Each compound carries the same safety rigor as any other intervention — for example, Beta-Carotene is flagged with a **contraindication** for smokers at supplement (not food) doses, reflecting the ATBC/CARET trial findings; Allicin carries a warfarin interaction; EGCG extract (not brewed tea) carries a rare hepatotoxicity caution.

### Extending the food layer

1. Add the compound to `PHYTOCHEMICAL_COMPOUNDS` in `app/knowledge_graph/food_seed_data.py` (mechanism, safety flags, drug interactions — same shape as `INTERVENTIONS` in `seed_data.py`).
2. Add the food(s) to `FOOD_INTERVENTIONS`.
3. Add the `(food, compound, richness, serving, note)` tuple(s) to `FOOD_COMPOUND_SOURCES`.
4. Add evidence claims to `FOOD_COMPOUND_EVIDENCE_CLAIMS` — `(compound, biomarker, effect, evidence_level, pmid)`.
5. Add the compound to the relevant pathway(s) in `app/pipeline/evidence_retriever.py` → `_PATHWAY_INTERVENTIONS` so it's pulled into evidence retrieval and reasoning.
6. Run `python scripts/seed_db.py` to populate the database; the static `COMPOUND_TO_FOOD_SOURCES` dict updates automatically since it's derived from the same source list.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Pydantic v2, Python 3.11+ |
| Auth | JWT (python-jose), bcrypt |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Database | PostgreSQL 15 + pgvector extension |
| Migrations | Alembic (async) |
| Task Queue | Celery + Redis |
| LLM | OpenAI (gpt-4o by default) |
| OCR | pdfplumber + pytesseract |
| HTTP client | httpx + tenacity (retries) |
| PHI encryption | cryptography (Fernet) |
| Logging | structlog |
| Testing | pytest-asyncio, respx (HTTP mocking), aiosqlite |
| Containers | Docker + Docker Compose |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone and configure

```bash
git clone https://github.com/xcross20/Herbagraph-.git
cd Herbagraph-
cp .env.example .env
```

### 2. Generate an encryption key

```bash
python scripts/generate_encryption_key.py
# Copy the output line into .env as ENCRYPTION_KEY=...
```

Edit `.env`:
```
OPENAI_API_KEY=your_api_key_here
ENCRYPTION_KEY=your_generated_fernet_key
SECRET_KEY=a_long_random_string_at_least_32_chars
```

### 3. Start services

```bash
docker-compose up -d
# or: make dev
```

### 4. Run migrations and seed the knowledge graph

```bash
make migrate        # runs alembic upgrade head
make seed           # runs scripts/seed_db.py
```

Or manually:
```bash
docker-compose exec api alembic upgrade head
docker-compose exec api python scripts/seed_db.py
```

### 5. Explore the API or the bare-bones frontend

- Frontend: [http://localhost:8000/](http://localhost:8000/) — a single-page explainable biological reasoning UI (`frontend/index.html`, served by the API, no build step). Upload one lab or run **Integrated Lab Analysis** across multiple files. Reports surface Executive Summary, Clinical Priorities, Diagnostic Optimization, and expandable sections (Biological Network, Intervention Library, Patient Data, Research Appendix) with a persistent sidebar. **Download Summary PDF** matches the on-screen view; **Download Full Report PDF** expands all sections for sharing. Guest auth is stored in `localStorage` on first visit — no login screen.
- **Demo lab files:** synthetic Quest/LabCorp/CSV samples in [`samples/lab_reports/`](samples/lab_reports/) — start with `demo_01_inflammatory_quest.txt` or `demo_03_comprehensive_quest.txt` (see that folder's README).
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `SECRET_KEY` | *(change in prod)* | JWT signing key — generate with `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | — | Fernet key for PHI encryption (required) |
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `LLM_MODEL` | `gpt-4o` | OpenAI model identifier |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker URL |
| `NCBI_API_KEY` | — | NCBI Entrez API key (optional; increases rate limit to 10 req/s) |
| `NCBI_EMAIL` | `dev@herbagraph.io` | Required by NCBI Entrez API terms of service |
| `USDA_KEY` | — | USDA FoodData Central API key for food entity enrichment ([signup](https://fdc.nal.usda.gov/api-key-signup.html)) |
| `UPLOAD_DIR` | `/tmp/herbagraph/uploads` | Encrypted lab file storage directory |
| `MAX_FILE_SIZE_MB` | `10` | Maximum lab file upload size |
| `DEBUG` | `false` | Enables verbose logging and relaxed CORS |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime |
| `DEIDENTIFY_BEFORE_LLM` | `true` | Strip PHI before sending to the LLM |
| `AUTH_PROVIDER` | `local` | `local` \| `clerk` \| `firebase` -- see [Auth & Multi-Patient Mode](#auth--multi-patient-mode) |
| `CLERK_SECRET_KEY` | — | Required if `AUTH_PROVIDER=clerk` |
| `FIREBASE_PROJECT_ID` | — | Required if `AUTH_PROVIDER=firebase` |

---

## API Reference

All endpoints are under `/api/v1/`. Auth uses Bearer JWT tokens.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new account |
| `POST` | `/auth/login` | Login; returns `access_token` + `refresh_token` |
| `GET` | `/auth/me` | Get current user |
| `DELETE` | `/auth/me` | Delete account and all associated data |
| `GET` | `/auth/profile` | Get health profile |
| `PUT` | `/auth/profile` | Update health profile |

#### Register
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "jane@example.com",
  "password": "SecurePass1"
}
```

**Password rules:** ≥8 characters, at least one uppercase letter and one digit.

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "email": "jane@example.com",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "jane@example.com",
  "password": "SecurePass1"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciO...",
  "refresh_token": "eyJhbGciO...",
  "token_type": "bearer"
}
```

#### Update Health Profile
```http
PUT /api/v1/auth/profile
Authorization: Bearer {token}
Content-Type: application/json

{
  "age_range": "35-45",
  "biological_sex": "F",
  "health_goals": ["reduce inflammation", "improve energy"],
  "current_medications": ["levothyroxine 50mcg"],
  "current_supplements": ["vitamin d"],
  "known_conditions": ["hypothyroidism"]
}
```

---

### Lab Reports

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/labs/upload` | Upload a lab file (PDF or text) |
| `GET` | `/labs` | List all lab reports |
| `GET` | `/labs/{id}` | Get a lab report with parsed results |
| `DELETE` | `/labs/{id}` | Delete a lab report and file |

#### Upload Lab Report
```http
POST /api/v1/labs/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file=@my_labs_2024.pdf
```

Supported formats: `.pdf`, `.txt`, `.csv`, `.png`, `.jpg`

**Response:** `201 Created`
```json
{
  "lab_report_id": "uuid",
  "task_id": "celery-task-id",
  "message": "Lab report uploaded. Processing has started.",
  "status": "processing"
}
```

**Poll status at** `GET /api/v1/labs/{lab_report_id}` until `status == "complete"`.

#### Get Lab Report Status
```http
GET /api/v1/labs/{lab_report_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "uuid",
  "original_filename": "my_labs_2024.pdf",
  "file_size_bytes": 84320,
  "status": "complete",
  "lab_results": [
    {
      "biomarker_name": "CRP",
      "value": 8.2,
      "unit": "mg/L",
      "reference_range_low": 0.0,
      "reference_range_high": 3.0,
      "status": "high"
    }
  ]
}
```

**Status values:** `pending` → `processing` → `complete` | `failed`

---

### Reports

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/reports/generate/{lab_report_id}` | (Re-)generate an evidence report; optional body `{ "knowledge_path": "legacy" \| "canonical" }` |
| `GET` | `/reports` | List all reports |
| `GET` | `/reports/{id}` | Get full recommendation report (includes `knowledge_path`) |
| `DELETE` | `/reports/{id}` | Delete a report |

### Knowledge registry

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/knowledge/coverage` | Entity counts by tier / review status |
| `GET` | `/knowledge/integrations?probe_usda=true` | USDA / LLM key readiness (+ optional live USDA probe) |
| `GET` | `/knowledge/entities` | List/search canonical entities |
| `POST` | `/knowledge/bootstrap/interventions` | Admin: seed registry from interventions catalog |
| `POST` | `/knowledge/enrichment/queue` | Admin: enqueue entity for enrichment |
| `POST` | `/knowledge/enrichment/run` | Admin: process enrichment queue batch |
| `POST` | `/knowledge/enrichment/seed-missing` | Admin: enqueue Tier A/B entities missing external IDs |

#### Get Recommendation Report
```http
GET /api/v1/reports/{report_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "uuid",
  "lab_report_id": "uuid",
  "overall_confidence": 0.71,
  "model_version": "0.1.0",
  "executive_summary": "Your labs show elevated systemic inflammation...",
  "biomarker_summary": {
    "total_biomarkers": 12,
    "abnormal_count": 4,
    "normal_count": 8,
    "categories_affected": {"inflammatory": 2, "metabolic": 1, "hepatic": 1}
  },
  "biomarker_interpretations": [
    {
      "biomarker_name": "CRP",
      "status": "high",
      "interpretation": "CRP is high (8.2 mg/L), which may be relevant to the biological pathways discussed below. This is a lab-value observation, not a diagnosis."
    }
  ],
  "biological_systems": [
    {
      "system_code": "inflammation",
      "system_name": "Inflammation",
      "signal_level": 3,
      "signal_label": "Strong Signal",
      "direction": "elevated",
      "confidence": "high",
      "drivers": ["CRP"],
      "pathways": [{"pathway_code": "NF_KB", "pathway_name": "NF-κB Inflammatory Signaling"}]
    }
  ],
  "pathway_activations": [
    {
      "pathway_code": "NF_KB",
      "pathway_name": "NF-κB Inflammatory Signaling",
      "activation_score": 0.88,
      "direction": "activated",
      "contributing_biomarkers": ["CRP", "IL-6"]
    }
  ],
  "recommendations": [
    {
      "rank": 1,
      "intervention_name": "Boswellia serrata",
      "category": "herb",
      "mechanism": "Selectively inhibits 5-LOX, reducing leukotriene B4 synthesis",
      "evidence_level": "moderate",
      "evidence_tier": "emerging",
      "evidence_tier_label": "Emerging Evidence",
      "confidence_score": 0.74,
      "typical_dose": "300mg AKBA-standardized extract 2x daily with food, per the cited trial",
      "rationale": "Directly addresses the elevated CRP finding via NF-κB inhibition.",
      "limitations": "Based on a single randomized trial in knee osteoarthritis patients; may not generalize to other causes of elevated CRP.",
      "safety_risk": "low",
      "safety_notes": ["Take with food to minimize GI upset"],
      "interactions": [],
      "is_regulated": false,
      "cited_study_ids": ["PMID:29480512"],
      "cited_urls": ["https://pubmed.ncbi.nlm.nih.gov/29480512/"]
    }
  ],
  "citations": [
    {
      "id": "PMID:29480512",
      "source": "pubmed",
      "title": "Boswellic acids reduce CRP in knee osteoarthritis: a randomized trial",
      "year": 2018,
      "study_type": "rct",
      "quality_score": 0.85
    }
  ],
  "clinician_questions": [
    "Should I be investigated for an occult infection source?",
    "Would anti-inflammatory medication be appropriate at this CRP level?"
  ],
  "safety_summary": {
    "overall_note": "No major drug-herb interactions detected.",
    "requires_clinician_review": false,
    "high_risk_interventions": []
  },
  "disclaimer": "⚠️ IMPORTANT DISCLAIMER: This report is generated by an AI system..."
}
```

---

### Evidence (Knowledge Graph)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/evidence/interventions` | Browse interventions (filter by category, search) |
| `GET` | `/evidence/interventions/{id}` | Get full intervention detail with safety data |
| `GET` | `/evidence/biomarkers` | List all biomarkers |
| `GET` | `/evidence/pathways` | List all pathways |
| `GET` | `/evidence/compounds/{compound_name}/food-sources` | Foods that are sources of a phytochemical compound |
| `GET` | `/evidence/foods/{food_name}/compounds` | Compounds a given food is a source of |

**Query params for `/evidence/interventions`:**
- `category`: `food \| herb \| phytochemical \| supplement \| exercise \| sleep \| stress_reduction \| medication \| peptide \| hormone \| environmental \| behavior` (see [Intervention Ontology](#intervention-ontology))
- `search`: Full-text name search
- `limit`: Max results (default 50, max 200)

#### Get Intervention Detail
```http
GET /api/v1/evidence/interventions/{intervention_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Boswellia serrata",
  "category": "herb",
  "description": "Indian frankincense resin extract standardized for boswellic acids.",
  "mechanism": "Selectively inhibits 5-LOX, reducing leukotriene B4 synthesis and downstream NF-κB activation.",
  "is_regulated": false,
  "regulation_note": null,
  "safety_flags": [
    {"condition": "pregnancy", "severity": "contraindication", "note": "Insufficient safety data in pregnancy; avoid."}
  ],
  "drug_interactions": [
    {"drug_name": "Warfarin", "severity": "moderate", "mechanism": "May potentiate anticoagulant effect.", "note": "Monitor INR if co-administered."}
  ],
  "compounds": [
    {
      "role": "primary active constituent",
      "compound": {
        "id": "uuid",
        "name": "AKBA (acetyl-11-keto-beta-boswellic acid)",
        "description": null,
        "primary_target": "5-LOX (5-lipoxygenase)",
        "pubchem_cid": null
      }
    }
  ]
}
```

#### Get Food Sources for a Compound
```http
GET /api/v1/evidence/compounds/Sulforaphane/food-sources
Authorization: Bearer {token}
```

**Response:**
```json
{
  "compound": "Sulforaphane",
  "food_sources": [
    {"food": "Broccoli Sprouts", "richness": "high", "typical_serving": "1/4 cup fresh sprouts", "note": "Roughly 10-100x the glucoraphanin concentration of mature broccoli."},
    {"food": "Broccoli", "richness": "moderate", "typical_serving": "1 cup steamed", "note": "Light steaming preserves myrosinase better than boiling."},
    {"food": "Brussels Sprouts", "richness": "moderate", "typical_serving": "1 cup cooked", "note": null},
    {"food": "Kale", "richness": "low", "typical_serving": "1-2 cups raw", "note": "Lower glucosinolate density than broccoli."}
  ]
}
```

---

### Patients (Clinic Mode)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/patients` | Create a Patient under the current account |
| `GET` | `/patients` | List Patients owned by the current account |
| `GET` | `/patients/{id}` | Get a single Patient |
| `DELETE` | `/patients/{id}` | Delete a Patient |

A **Patient** is only needed in clinic mode -- a `clinician` account managing multiple patients (see [Auth & Multi-Patient Mode](#auth--multi-patient-mode) below). Individual self-service users never need to create one; `POST /labs/upload` works exactly as documented above with no `patient_id`.

```http
POST /api/v1/patients
Authorization: Bearer {token}
Content-Type: application/json

{"age": 42, "biological_sex": "F"}
```

To attach a lab upload to a Patient, pass `patient_id` as an additional multipart form field on `POST /labs/upload`.

### Feedback

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/reports/{report_id}/feedback` | Submit a 1-5 rating (+ optional comment) on a report |
| `GET` | `/reports/{report_id}/feedback` | List feedback submitted for a report |

```http
POST /api/v1/reports/{report_id}/feedback
Authorization: Bearer {token}
Content-Type: application/json

{"rating": 4, "comment": "The dosing context was helpful."}
```

### Response Tracking (Biological Response Engine)

HerbaGraph's core pipeline (above) answers "here's information about this biomarker/pathway." The **Response Validation Module** adds a time dimension so it can also answer "did this biological system change between two lab snapshots for the same tracked intervention?"

Flow: `Baseline Labs → Intervention → Follow-up Labs → Biological Response Report`. A `ResponseTracking` record links a baseline `LabReport` to a later follow-up `LabReport` for one named intervention.

This is **pure arithmetic, not ML or an LLM call**: each biomarker's baseline and follow-up values are compared by distance to that biomarker's own optimal range (not a naive "went up/down," since biomarkers like Ferritin or TSH are unhealthy in both directions), then rolled up into the same 7 biological systems used elsewhere in the app. It never claims the tracked intervention *caused* any change -- every response report carries an explicit non-causality disclaimer, and any evidence shown alongside it is read-only context about the intervention, not a causal claim.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/tracking` | Start tracking: intervention name + baseline lab report (+ optional patient, start date) |
| `GET` | `/tracking` | List tracking records owned by the current account |
| `GET` | `/tracking/{id}` | Get a single tracking record |
| `DELETE` | `/tracking/{id}` | Delete a tracking record |
| `POST` | `/tracking/{id}/follow-up` | Attach a follow-up lab report once it's available |
| `GET` | `/tracking/{id}/response` | Generate the Biological Response Report (409 until a follow-up is attached) |

```http
POST /api/v1/tracking
Authorization: Bearer {token}
Content-Type: application/json

{"intervention_name": "Curcumin", "baseline_lab_report_id": "uuid"}
```

```http
POST /api/v1/tracking/{id}/follow-up
Authorization: Bearer {token}
Content-Type: application/json

{"follow_up_lab_report_id": "uuid"}
```

```http
GET /api/v1/tracking/{id}/response
Authorization: Bearer {token}
```

**Response:** `200 OK`
```json
{
  "intervention_name": "Curcumin",
  "baseline_date": "2024-01-01T00:00:00Z",
  "follow_up_date": "2024-02-26T00:00:00Z",
  "duration_days": 56,
  "biomarker_changes": [
    {
      "biomarker_name": "CRP",
      "baseline_value": 3.6,
      "follow_up_value": 1.2,
      "unit": "mg/L",
      "percent_change": -66.7,
      "direction": "improved",
      "direction_label": "Improved"
    }
  ],
  "system_responses": [
    {
      "system_code": "inflammation",
      "system_name": "Inflammation",
      "response": "improved",
      "response_label": "Improved",
      "confidence": "high",
      "contributing_biomarkers": ["CRP", "Ferritin"]
    }
  ],
  "evidence_context": [
    {
      "intervention_name": "Curcumin",
      "summary": "RCTs suggest curcumin supplementation has been associated with reductions in inflammatory markers in some populations.",
      "evidence_level": "moderate",
      "pmid": "12345678"
    }
  ],
  "disclaimer": "The biomarker changes below are observed differences between two lab snapshots. This platform presents those changes alongside relevant published evidence about the tracked intervention, but it does not infer causality -- it cannot determine whether the intervention caused any change, whether another factor was responsible, or what would have happened without it."
}
```

Together, the two products complement each other: the existing pipeline is an **Evidence Intelligence Engine** (upload labs, understand biomarkers, map pathways, review evidence, assess safety), and Response Tracking is a **Biological Response Engine** (compare baseline/follow-up biomarkers, quantify change over time, relate that change to published evidence for the tracked intervention -- without ever claiming the intervention caused it).

---

## Privacy Design

HerbaGraph follows the **HHS Safe Harbor de-identification method** (45 CFR §164.514(b)):

### Data Separation
- **User identity** (email, hashed password) lives in the `users` table.
- **Health data** (lab results, recommendations) lives in `health_profiles`, linked by a random UUID — not the user's email.
- Neither table references the other's PII directly.

### Encryption at Rest
- Lab files on disk are stored with **Fernet symmetric encryption** (AES-128-CBC + HMAC-SHA256).
- The file path stored in the database is itself Fernet-encrypted.
- The encryption key is loaded from the environment, never committed to source control.

### De-identification Before LLM
When the pipeline sends data to the LLM:
- Names, exact dates, MRNs, addresses, phone numbers, and SSNs are stripped by regex before transmission.
- Only `age_range` (e.g. "35-45"), biological sex, health goals, medications, and lab values (without any identifiers) are sent.
- Controlled by `DEIDENTIFY_BEFORE_LLM=true`.

### No Free-form LLM Invention
The LLM is instructed to reason **only from evidence snippets retrieved in the current session**. It cannot hallucinate citations — all cited PMIDs are verified at retrieval time.

---

## Evidence Grading

Every recommendation carries an explicit **evidence tier** (`evidence_tier` / `evidence_tier_label`) so the platform never implies all evidence is equally strong. Unlike `evidence_level` (a per-claim strength rating baked into confidence scoring), the tier is a user-facing label **derived deterministically from the studies actually cited** for that recommendation — never asserted by the LLM, so it can't drift from what was really retrieved (see `report_generator.determine_evidence_tier`).

| Tier | Label | Criteria |
|---|---|---|
| `established` | **Established Evidence** | A cited meta-analysis or systematic review, or ≥2 cited RCTs |
| `emerging` | **Emerging Evidence** | A single cited RCT, or cited cohort/case-control (human observational) studies |
| `preclinical` | **Preclinical Evidence** | Only animal/cell-culture (preclinical) studies cited |
| `research_hypothesis` | **Research Hypothesis** | No citation could be resolved against retrieved evidence — should not normally occur, since Stage 5 already requires ≥1 valid citation per recommendation, but this is the safety-net default |
| `traditional_use` | Traditional Use (Ayurveda/TCM) | Reserved for a future traditional-medicine evidence source |
| `historical_ethnobotanical` | Historical/Ethnobotanical Use | Reserved for a future ethnobotanical evidence source |

**HerbaGraph today only ever assigns the first four tiers.** The evidence hierarchy conceptually extends to traditional/historical use (Ayurveda, TCM, ethnobotanical records), but the platform does not currently retrieve from or label anything as traditional-medicine evidence — PubMed, ClinicalTrials.gov, and Europe PMC are all modern clinical/preclinical literature sources. Rather than blur that distinction, those two tiers exist in the schema but are never produced automatically; wiring up a traditional-medicine corpus is a natural Phase 2 extension.

Every recommendation also states its own limits in plain language via `limitations` (e.g. "based on a single small RCT; short follow-up"), and `rationale` states why it was surfaced (which abnormal biomarker/pathway it addresses) — "show your work," not a black-box verdict.

---

## Confidence Scoring

Each recommendation receives a composite confidence score (0–1):

```
score = (0.35 × evidence_strength)
      + (0.25 × study_quality)
      + (0.20 × biomarker_relevance)
      + (0.10 × pathway_relevance)
      + (0.10 × (1 - safety_risk))
```

### Evidence Strength (`evidence_level`)
| Level | Score |
|---|---|
| `high` (meta-analysis/systematic review) | 0.95 |
| `moderate` (RCTs) | 0.65 |
| `low` (cohort, case-control) | 0.35 |
| `preclinical` | 0.20 |

### Study Quality (from retrieved evidence)
Weighted average of `quality_score` across evidence snippets:

| Study Type | Weight |
|---|---|
| Meta-analysis | 1.00 |
| Systematic review | 0.90 |
| RCT | 0.85 |
| Cohort study | 0.60 |
| Case-control | 0.45 |
| Preclinical | 0.20 |

### Safety Risk Deduction
| Risk Level | Safety Score |
|---|---|
| `low` | 0.00 (no deduction) |
| `moderate` | 0.40 |
| `high` | 0.75 |
| `contraindicated` | 1.00 (excluded entirely) |

---

## Running Tests

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install pytest-asyncio aiosqlite respx

# Run all tests
make test
# or
pytest

# Run with coverage
make coverage
# or
pytest --cov=app --cov-report=html

# Run only unit tests (fast, no I/O)
pytest -m unit

# Run only API tests
pytest tests/test_api/

# Run only pipeline tests
pytest tests/test_pipeline/
```

### Test Architecture
- **Unit tests** (`@pytest.mark.unit`): No database, no network. All external services mocked.
- **Integration tests** (`tests/test_api/`): Use SQLite in-memory database via test dependency override. HTTP clients use `respx` mock interceptors.
- **No real API calls** are made during testing. PubMed, OpenAI, PubChem, and ClinicalTrials.gov are all mocked with `respx` or `unittest.mock.AsyncMock`.

---

## Development Guide

### Project Layout

```
herbagraph/
├── app/
│   ├── api/
│   │   ├── deps.py              # FastAPI shared dependencies
│   │   └── v1/
│   │       ├── auth.py          # Authentication routes
│   │       ├── evidence.py      # Knowledge graph exploration
│   │       ├── labs.py          # Lab upload and management
│   │       ├── reports.py       # Recommendation reports
│   │       └── router.py        # Router aggregator
│   ├── config.py                # Pydantic settings
│   ├── core/
│   │   ├── privacy.py           # Fernet encryption + de-identification
│   │   └── security.py          # JWT + bcrypt
│   ├── database.py              # Async SQLAlchemy engine
│   ├── integrations/
│   │   ├── pubmed.py            # NCBI Entrez API
│   │   ├── clinicaltrials.py    # ClinicalTrials.gov API v2
│   │   ├── pubchem.py           # PubChem PUG-REST
│   │   └── europepmc.py         # Europe PMC REST
│   ├── knowledge_graph/
│   │   └── seed_data.py         # Canonical botanical/nutraceutical data
│   ├── main.py                  # FastAPI app entry point
│   ├── models/                  # SQLAlchemy ORM models
│   ├── pipeline/                # 7-stage processing pipeline
│   │   ├── lab_parser.py
│   │   ├── biomarker_normalizer.py
│   │   ├── pathway_mapper.py
│   │   ├── evidence_retriever.py
│   │   ├── llm_reasoner.py
│   │   ├── safety_layer.py
│   │   ├── report_generator.py
│   │   └── orchestrator.py
│   ├── schemas/                 # Pydantic I/O schemas
│   └── workers/
│       └── tasks.py             # Celery task definitions
├── alembic/                     # Database migrations
├── scripts/
│   ├── generate_encryption_key.py
│   └── seed_db.py
├── tests/
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── requirements.txt
```

### Adding a New Biomarker

1. Add the entry to `app/pipeline/biomarker_normalizer.py` in `_ALIAS_MAP` (aliases → canonical name) and `_REFERENCE_DATA` (reference ranges).
2. Optionally add pathway rules in `app/pipeline/pathway_mapper.py`.
3. Add to `app/knowledge_graph/seed_data.py` → `BIOMARKERS` for the database.
4. Run `python scripts/seed_db.py` to populate the database.

### Adding a New Intervention

1. Add to `app/knowledge_graph/seed_data.py` → `INTERVENTIONS` with:
   - `name`, `category` (one of the [Intervention Ontology](#intervention-ontology) values), `description`, `mechanism`
   - `compounds`: a list of `{"name", "primary_target", "role", "pubchem_cid"}` dicts (the Compound/Target layer -- leave `pubchem_cid` as `None`; it resolves on demand via `app/integrations/pubchem.py`)
   - `safety_flags` (pregnancy, kidney, liver, autoimmune, etc.)
   - `drug_interactions` (with severity and mechanism)
2. Add to the pathway-to-intervention mapping in `app/pipeline/evidence_retriever.py` → `_PATHWAY_INTERVENTIONS`.
3. If interactions are not in the database, add them to `app/pipeline/safety_layer.py` → `_DRUG_HERB_INTERACTIONS`.
4. Run `python scripts/seed_db.py`.

### Adding a New Pathway

1. Add to `app/pipeline/pathway_mapper.py` → `_PATHWAY_CONFIGS` with weight map.
2. Add the intervention mapping to `app/pipeline/evidence_retriever.py` → `_PATHWAY_INTERVENTIONS`.
3. Add to `app/knowledge_graph/seed_data.py` → `PATHWAYS`.

### Database Migrations

```bash
# After changing SQLAlchemy models:
alembic revision --autogenerate -m "describe your change"

# Apply migrations:
alembic upgrade head

# Rollback one step:
alembic downgrade -1
```

### Makefile Targets

```bash
make dev          # Docker Compose up (API + worker + db + redis)
make test         # pytest
make coverage     # pytest with HTML coverage report
make migrate      # alembic upgrade head
make seed         # python scripts/seed_db.py
make lint         # ruff + mypy
make format       # ruff format
make worker       # start Celery worker
make logs         # docker-compose logs -f
make clean        # stop and remove containers + volumes
```

---

## Knowledge Graph

The seeded knowledge graph includes:

**266 Biomarkers** — core metabolic panel plus infectious disease, celiac serology, allergy IgE, pharmacogenomics, cultures, and more. Each entry has a `result_kind` (`numeric`, `qualitative`, `culture`, `genotype`) used by the test-type router.

**28 Pathways** — 16 signaling + 12 etiological. Signaling pathways roll up into **7 user-facing Biological Systems**. Etiological pathways power root-cause recommendation trees. See [Recommendation Trees & Etiological Pathways](#recommendation-trees--etiological-pathways).

**76 Tier A Interventions** (+ 10 clinical peptides) — every entry has real compounds/targets, safety flags, and PMID-linked evidence claims with `recommendation_intent`:

| Category | Count | Examples |
|---|---|---|
| Herbs | 16 | Mastic Gum, DGL Licorice, Boswellia, Turmeric |
| Supplements / lifestyle | 19 | Berberine, Zinc Carnosine, Glutamine, Gluten Elimination Diet |
| Phytochemicals | 16 | Sulforaphane, Curcumin, Allicin, Quercetin |
| Foods | 15 | Broccoli Sprouts, Garlic, Blueberries |
| Peptides | 10 | Semaglutide, Tirzepatide (regulated, clinical evidence only) |

**49 Evidence Claims** — each links `intervention_name` → `biomarker` and/or `pathway_code` with `recommendation_intent` (`primary`, `collateral`, `context_only`, `nutritional_repletion`).

**15 Curated Food→Compound Links** — e.g. Broccoli Sprouts → Sulforaphane (high), Garlic → Allicin (high). See [Food → Compound Layer](#food--compound-layer).

---

## Safety Layer

The safety layer checks every LLM-generated recommendation before it appears in the final report, in the explicit staged order described in [Stage 6](#stage-6-safety-layer).

### Drug-Herb Interactions Tracked
| Drug/Class | Flagged Herbs |
|---|---|
| Warfarin | Boswellia, Berberine, Curcumin, Omega-3, CoQ10, St. John's Wort, Ginkgo, Allicin/Garlic |
| Metformin | Berberine |
| SSRIs/SNRIs | St. John's Wort |
| Cyclosporine | Berberine, St. John's Wort |
| Levothyroxine | Ashwagandha, ALA |
| Immunosuppressants | Ashwagandha |
| Insulin/antidiabetics | ALA, Berberine, Chromium |
| Statins | Milk Thistle |
| Chemotherapy | Curcumin, Quercetin |

### Automatic Exclusions (Contraindication Check)
- **Pregnancy**: Berberine, Ashwagandha, high-dose Curcumin, Boswellia
- **Severe CKD**: Magnesium, Potassium, high-dose Vitamin D
- **Autoimmune disease (on immunosuppressants)**: Ashwagandha, Echinacea

### Kidney/Liver Warning (Soft Flag, Not an Exclusion)
Unlike the exclusions above, a liver-disease condition on the patient's health profile adds a visible caution note rather than removing the recommendation outright — e.g. concentrated EGCG extract's rare hepatotoxicity signal at high doses is surfaced as a `MODERATE` safety-risk note, not a hard block.

### Regulated / Emerging Interventions
Peptides (BPC-157, TB-500), GLP-1 receptor agonists, and similar compounds are clearly labeled with `is_regulated: true` and a regulation note. The system never recommends prescription-only compounds — it only surfaces them in the evidence context with appropriate labeling.

---

## Auth & Multi-Patient Mode

Two pieces of infrastructure exist for scaling past a single-person self-service tool, both additive and both fully optional -- the default individual-user flow documented everywhere above is completely unaffected by either.

### Pluggable auth providers

**Don't build authentication yourself in production -- use a provider like Clerk or Firebase Auth.** HerbaGraph's default (`AUTH_PROVIDER=local`, unset by default) is its own JWT + bcrypt implementation, which is what every test and every flow in this README runs against. `app/core/auth_providers.py` is the integration point for switching to a real provider:

```
AUTH_PROVIDER=clerk
CLERK_SECRET_KEY=sk_...
```
or
```
AUTH_PROVIDER=firebase
FIREBASE_PROJECT_ID=...
```

Selecting `clerk` or `firebase` without the matching credential raises a clear `501` configuration error (`"AUTH_PROVIDER=clerk but CLERK_SECRET_KEY is not set..."`) rather than silently falling back to local auth. Even with the credential set, actual token verification against Clerk/Firebase is a documented stub, not yet implemented -- wiring it up (verify the session token via the provider's backend SDK, then map the returned external user id to a local `User` row) is the next step once real provider credentials exist. Until then, leave `AUTH_PROVIDER` unset and everything works exactly as documented.

### Multi-patient (clinic) mode

The `users` table gained two columns matching a clinic-account shape:

| Column | Description |
|---|---|
| `role` | `individual` (default) or `clinician` |
| `clinic_name` | Optional display name for a clinician's practice |

A new **`Patient`** table sits between `User` and `LabReport` for the clinic case -- a clinician account managing multiple patients. Like `HealthProfile`, a `Patient` carries no name or other direct identifier, just a random UUID plus non-identifying `age`/`biological_sex`. `LabReport.patient_id` is a nullable FK to it: individual users never set it (their reports belong directly to their own `User` row, exactly as before this column existed); a clinician passes `patient_id` on `POST /labs/upload` to attach it to one of their Patients instead.

```
Users
  ↓ (role=clinician)
Patients (random UUID, age, sex -- no name)
  ↓
LabReports (patient_id optional)
  ↓
LabResults
  ↓
RecommendationReports
  ↓
Feedback (rating 1-5 + optional comment)
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run tests: `make test`
4. Submit a pull request

Please follow existing code conventions (type hints, structlog, async everywhere, test coverage for new pipeline stages).
