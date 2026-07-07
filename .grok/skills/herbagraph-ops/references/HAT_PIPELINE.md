# HerbaGraph × Engineering Operating Manual

Quick reference for hat discipline. Full manual: user-provided Engineering Operating Manual.

## Pipeline map

| Hat | HerbaGraph focus | Artifact |
|---|---|---|
| PM | What user-visible outcome? Testable claims? | Slice spec in BACKLOG.json |
| Architect | Catalog, pipeline stages, DB entities | Seam grades + ADR snippet |
| Staff engineer | Where will this silently fail? | Risk map (3–5 bullets) |
| Implementer | Vertical slice in `app/`, `frontend/`, `samples/` | Code + tests |
| QA | Spec-derived tests + scenarios | pytest + validate_* scripts |
| Reviewer | Cold diff prosecution | Review notes (or /review file) |
| SRE | reseed, remap, docker | Ops log in slice artifacts |
| Tech lead | BACKLOG + IMP updates | Updated ops/BACKLOG.json |

## HerbaGraph verification seams

```
lab file → parse_lab_file → normalize_lab_results → map_pathways
  → route_recommendation_trees → retrieve_evidence → generate_reasoning
  → check_safety → generate_report → API → frontend renderReport
```

Cut tests at each seam. Bugs cluster at:
- **normalizer ↔ alias map** (mean-cell, OCR reversal, custom profile)
- **pathway_mapper ↔ catalog names** (must be canonical at report time)
- **catalog_evidence ↔ abnormal biomarkers** (pathway-only claims)
- **persisted lab_results ↔ report reload** (stale biomarker_name)
- **latest_report_id ↔ UI fetch** (stale report)

## Standing hotspots (Appendix C)

| Hotspot | HerbaGraph instance |
|---|---|
| Boundaries | Parser output vs normalizer alias resolution |
| Shared state | `lab_results.biomarker_name`, `health_profiles.custom_biomarkers` |
| Time | Guest session localStorage; async Celery report stages |
| Error paths | Empty `pathway_activations` with abnormal labs |
| Config | OPENAI_API_KEY for LLM stage; Docker vs local DB |
| Migrations | reseed KG, remap lab rows, alembic schema |
| Freshly changed | Any alias or pathway rule — rerun macrocytic scenario |

## Definition of done

See `ops/BACKLOG.json` → `definition_of_done`. **Non-negotiable:** `scripts/ci_gates.sh` exit 0.

## Improvement cadence

- End of every slice: ≥1 IMP-* reviewed
- Weekly (or when user says continue): `/herbagraph-ops improve` sweep
- After any user-reported "empty UI" bug: add scenario + IMP for root cause class