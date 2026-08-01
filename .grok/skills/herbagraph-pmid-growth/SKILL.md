---
name: herbagraph-pmid-growth
description: >
  Continuously grow real PubMed-backed evidence claims for HerbaGraph catalog
  interventions. Use when the user runs /herbagraph-pmid-growth, asks to expand
  PMIDs, run a marathon/hour-long growth session, remediate title mismatches,
  fill claim-less interventions, or schedule ongoing evidence growth. Never invent PMIDs.
metadata:
  short-description: "Grow real PMID evidence claims (daily + hour marathon)"
---

# HerbaGraph PMID Growth

You expand **real, verifiable** literature claims for interventions in the HerbaGraph catalogs. Predicted graph edges are not enough for M2/M4 depth — this skill fills **PMID-backed** claims (Tier A / longtail / generated).

## Hard rules

1. **Never invent PMIDs.** Every PMID must be a real PubMed record.
2. Prefer interventions with **zero claims** first (`claimless`), then **depth** (extra PMIDs until `min_claims`).
3. After edits run:
   - `python3 scripts/audit_pmid_integrity.py`
   - `HERBAGRAPH_PMID_AUDIT_STRICT=1 python3 scripts/audit_pmid_integrity.py` when network is available
   - `python3 scripts/audit_evidence_gaps.py`
   - `python3 scripts/validate_seed_counts.py`
4. Intervention names in claims **must exist** in seeder catalogs.
5. Update `scripts/audit_pmid_integrity.py` `_INTERVENTION_KEYWORDS` for new names (batch script does this automatically).
6. Commit with a message that lists intervention count / mode.

## Source of truth

| Path | Role |
|------|------|
| `app/knowledge_graph/tier_a_evidence.py` | Core Tier A claims (+ extends longtail + generated) |
| `app/knowledge_graph/catalog_longtail_claims.py` | Curated high-traffic long-tail |
| `app/knowledge_graph/generated_pmid_claims.py` | **Auto cloud batches** (append-only via batch script) |
| `scripts/pmid_growth_batch.py` | NCBI batch engine (daily + marathon) |
| `scripts/audit_pmid_integrity.py` | Denylist + keyword map |
| `.github/workflows/pmid-growth.yml` | Cloud schedule + manual dispatch |

## Invocation

### `/herbagraph-pmid-growth` (default — interactive batch)

1. Queue:
   ```bash
   python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py --limit 25
   ```
2. Pick **10–25** interventions; search PubMed; add claims; run integrity gates; commit if asked.

### `/herbagraph-pmid-growth strict`

Must pass `HERBAGRAPH_PMID_AUDIT_STRICT=1`.

### `/herbagraph-pmid-growth remediate`

Replace TITLE_MISMATCH / KNOWN_MISMATCH PMIDs; re-audit until clean.

### `/herbagraph-pmid-growth schedule` (cloud daily)

GitHub Actions daily at **14:00 UTC**, limit **150**, mode **claimless**.

Secrets (repo Actions): `NCBI_API_KEY`, `NCBI_EMAIL`.

### `/herbagraph-pmid-growth marathon` (hour-long — thousands)

**Use this when the user wants a long continuous run / thousands of results.**

Runs the batch engine until **wall-clock duration** or **limit**, whichever first. Hybrid queue = claimless first, then depth (extra PMIDs per intervention up to `min_claims`).

| Setting | Marathon default |
|---------|------------------|
| Duration | **60 minutes** (`--max-seconds 3600`) |
| Limit | **4000** accepted (hard cap 8000) |
| Mode | **hybrid** |
| min_claims | **5** (multiple PMIDs per intervention) |
| Checkpoint | every **50** accepts (crash-safe) |
| Expected yield | ~**2000–3500**/hour with `NCBI_API_KEY`; ~**800–1500**/hour without |
| Job timeout | 120 minutes (install + gates + PR) |

#### Cloud (preferred)

```bash
# Via GitHub CLI — hour marathon on main
gh workflow run "PMID growth (cloud)" --ref main \
  -f mode=marathon \
  -f limit=4000 \
  -f duration_minutes=60 \
  -f dry_run=false

# Or: Actions → PMID growth (cloud) → Run workflow
#   mode: marathon
#   limit: 4000
#   duration_minutes: 60
```

#### Local

```bash
export NCBI_API_KEY=...   # strongly recommended
export NCBI_EMAIL=you@example.com

python3 scripts/pmid_growth_batch.py \
  --max-seconds 3600 \
  --limit 5000 \
  --mode hybrid \
  --min-claims 5 \
  --checkpoint-every 50 \
  --write \
  --json-out ops/pmid_growth_last_run.json

# Then gates + PR/commit as usual
python3 scripts/audit_pmid_integrity.py
python3 scripts/audit_evidence_gaps.py
python3 scripts/validate_seed_counts.py
```

#### Agent behavior for marathon

1. Confirm `NCBI_API_KEY` is set in GitHub secrets (or local env). Log must show `api_key=yes`.
2. Prefer **cloud** (`gh workflow run` / Actions) so laptop can sleep.
3. Do **not** invent PMIDs or lower title-match quality for speed.
4. After run: open/merge the auto PR (`chore/pmid-growth-auto`); summarize `accepted`, `elapsed`, `stop_reason`, `est_accepted_per_hour` from `ops/pmid_growth_last_run.json`.
5. If queue starves (`stop_reason=queue_exhausted` early): raise `--min-claims` (e.g. 5) or expand catalog; claimless alone caps near catalog size (~800–900 names).

## Queue modes

| Mode | Who gets searched |
|------|-------------------|
| `claimless` | Zero PMID claims (daily default) |
| `depth` | Has claims but fewer than `min_claims` |
| `hybrid` | Claimless first, then depth (marathon) |

```bash
python3 .grok/skills/herbagraph-pmid-growth/scripts/pmid_growth_queue.py --mode hybrid --limit 50
```

## Batch size guide

| Goal | Command / input |
|------|-----------------|
| Daily steady | limit 100–150, mode daily / claimless |
| First quality PR | limit 100, dry_run optional |
| **Hour / thousands** | **mode=marathon, duration=60, limit=4000** |
| Interactive review | 10–25 curated claims |

Throughput (measured with key): ~**1.1 s/accepted** → theoretical ~**3200/hour**; real ~**2000–3500** after skips.

## Claim template

```python
{"intervention_name": "Ginkgo biloba", "biomarker_name": "CRP", "pathway_code": "NF_KB",
 "effect": "decreases", "evidence_level": "moderate", "pmid": "14602503",
 "recommendation_intent": "primary",
 "summary": "One sentence: population + design + outcome; adjunct framing."},
```

- Curated high-traffic → `catalog_longtail_claims.py`
- Automated cloud / marathon → `generated_pmid_claims.py`

## Non-goals

- Inventing PMIDs or fake trials
- Clinical validation / medical advice
- Replacing predicted graph edges (they stay until PMID exists)
- Running marathon without integrity gates after write
