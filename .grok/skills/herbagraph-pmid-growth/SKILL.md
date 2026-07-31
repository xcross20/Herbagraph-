---
name: herbagraph-pmid-growth
description: >
  Continuously grow real PubMed-backed evidence claims for HerbaGraph catalog
  interventions that lack PMIDs. Use when the user runs /herbagraph-pmid-growth,
  asks to expand PMIDs, remediate title mismatches, fill claim-less interventions,
  or schedule ongoing evidence growth. Never invent PMIDs.
metadata:
  short-description: "Grow real PMID evidence claims"
---

# HerbaGraph PMID Growth

You expand **real, verifiable** literature claims for interventions in the HerbaGraph catalogs. Predicted graph edges are not enough for M2/M4 depth — this skill fills **PMID-backed** `TIER_A_EVIDENCE_CLAIMS` / longtail claims.

## Hard rules

1. **Never invent PMIDs.** Every PMID must be a real PubMed record.
2. Prefer interventions with **zero claims** first, then thin pathways (`scripts/audit_evidence_gaps.py`).
3. After edits run:
   - `python3 scripts/audit_pmid_integrity.py`
   - `HERBAGRAPH_PMID_AUDIT_STRICT=1 python3 scripts/audit_pmid_integrity.py` when network is available
   - `python3 scripts/audit_evidence_gaps.py`
   - `python3 scripts/validate_seed_counts.py`
4. Intervention names in claims **must exist** in seeder catalogs (`INTERVENTIONS` / foods / phytochemicals / peptides).
5. Update `scripts/audit_pmid_integrity.py` `_INTERVENTION_KEYWORDS` for new intervention names.
6. Add or extend a lab scenario when a claim unlocks a new rec tree path (optional for pure density fills).
7. Commit with a message that lists intervention names and claim count.

## Source of truth

| Path | Role |
|------|------|
| `app/knowledge_graph/tier_a_evidence.py` | Core Tier A claims |
| `app/knowledge_graph/catalog_longtail_claims.py` | High-traffic long-tail batch |
| `app/knowledge_graph/lifestyle_evidence.py` | Lifestyle claims |
| `app/knowledge_graph/peptide_catalog.py` | Peptide claims |
| `scripts/audit_pmid_integrity.py` | Denylist + keyword map |
| `scripts/audit_evidence_gaps.py` | Pathway min routable claims |
| `ops/BACKLOG.json` | Record IMP/slice status |

## Invocation

### `/herbagraph-pmid-growth` (default — one batch)

1. Run queue script:
   ```bash
   python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py --limit 25
   ```
2. Pick **10–25** interventions from the queue (highest priority first).
3. For each intervention:
   - Search PubMed (tooling or `esearch`/`esummary`) for human trials / meta-analyses when possible.
   - Add claim(s) with: `intervention_name`, `biomarker_name` and/or `pathway_code`, `effect`, `evidence_level`, `pmid`, `recommendation_intent`, `summary`.
   - Intent rules: `nutritional_repletion` for deficiency repletion; `primary` for tree-driving recs; `context_only` for PGx; `collateral` for secondary.
4. Add keywords to `_INTERVENTION_KEYWORDS`.
5. Run integrity + evidence-gap gates.
6. Update `ops/BACKLOG.json` (new SLICE or mark IMP progress).
7. Commit and push if the user wants shipping.

### `/herbagraph-pmid-growth strict`

Same as default, but **must** pass `HERBAGRAPH_PMID_AUDIT_STRICT=1`.

### `/herbagraph-pmid-growth remediate`

1. Run strict audit; collect TITLE_MISMATCH / KNOWN_MISMATCH.
2. Replace bad PMIDs with verified ones.
3. Re-run strict audit until 0 failures.

### `/herbagraph-pmid-growth schedule` (cloud — laptop can be off)

**Primary path: GitHub Actions** (`.github/workflows/pmid-growth.yml`)

| Setting | Value |
|---------|--------|
| Schedule | Daily **14:00 UTC** |
| Default target | **150** accepted claims |
| Range | 50–200 (workflow_dispatch input) |
| Runtime for 100 | ~**2.5–4 minutes** without NCBI key; ~**1.5–3 min** with `NCBI_API_KEY` |
| Output | PR branch `chore/pmid-growth-auto` |
| Files | `app/knowledge_graph/generated_pmid_claims.py`, `ops/pmid_growth_last_run.json` |

```bash
# Local timed batch
python3 scripts/pmid_growth_batch.py --limit 100 --dry-run
python3 scripts/pmid_growth_batch.py --limit 150 --write

# Manual cloud: GitHub → Actions → "PMID growth (cloud)" → Run workflow
# Secrets (optional but recommended): NCBI_API_KEY, NCBI_EMAIL
```

Grok durable schedulers are **not** a substitute — they depend on the agent platform. Use **GitHub Actions** for true always-on cloud.

## Claim template

```python
{"intervention_name": "Ginkgo biloba", "biomarker_name": "CRP", "pathway_code": "NF_KB",
 "effect": "decreases", "evidence_level": "moderate", "pmid": "14602503",
 "recommendation_intent": "primary",
 "summary": "One sentence: population + design + outcome; adjunct framing."},
```

- Curated high-traffic → `catalog_longtail_claims.py`
- Automated cloud batches → `generated_pmid_claims.py` (via `pmid_growth_batch.py`)

## Batch size

- Cloud default: **100–150/day** (up to **200**)
- Interactive Grok review batches: **10–25** still fine
- Claim routing is code-side; reseed only if DB evidence consumers matter

## Non-goals

- Inventing PMIDs or fake trials
- Clinical validation / medical advice
- Replacing predicted graph edges (they stay for long-tail until PMID exists)
