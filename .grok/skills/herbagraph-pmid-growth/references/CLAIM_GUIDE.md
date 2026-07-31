# PMID claim guide (quick reference)

## Required fields

| Field | Notes |
|-------|--------|
| `intervention_name` | Exact catalog name |
| `biomarker_name` | Optional; use for biomarker-direct trees |
| `pathway_code` | Prefer one of the 28 `PATHWAY_DISPLAY_NAMES` codes |
| `effect` | `increases` \| `decreases` |
| `evidence_level` | `high` \| `moderate` \| `low` \| `preclinical` |
| `pmid` | Digits only string |
| `recommendation_intent` | `primary` \| `collateral` \| `context_only` \| `nutritional_repletion` |
| `summary` | One factual sentence; adjunct framing |

## Intent cheat sheet

- **nutritional_repletion** — correcting a measured deficiency (Iron, B12, Vit D, …)
- **primary** — main rec for the active tree (etiological mastic, signaling curcumin, …)
- **collateral** — useful adjunct, not first-line
- **context_only** — PGx / exposure history; not a directive to start therapy

## Where to put claims

- High-traffic catalog fills → `catalog_longtail_claims.py`
- Core clinical Tier A → `tier_a_evidence.py`
- Lifestyle methods → `lifestyle_evidence.py`
- Peptides → `peptide_catalog.py` `PEPTIDE_EVIDENCE_CLAIMS`

## After each batch

```bash
python3 scripts/audit_pmid_integrity.py
HERBAGRAPH_PMID_AUDIT_STRICT=1 python3 scripts/audit_pmid_integrity.py  # if network OK
python3 scripts/audit_evidence_gaps.py
python3 scripts/validate_seed_counts.py
```
