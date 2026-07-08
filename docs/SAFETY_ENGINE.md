# HerbaGraph Safety Engine v1.0

The Safety Engine is an **independent module** that evaluates candidate interventions **before** evidence ranking and report assembly. It informs clinicians — it does not prescribe, diagnose, or remove options silently.

## Pipeline position

```
Labs → Knowledge Graph → Clinical Reasoning (LLM)
                              ↓
                      Safety Engine v1.0
                              ↓
                   Evidence Ranking (confidence)
                              ↓
                      Report Generation
```

## Design principles

1. **Transparency over certainty** — every warning includes mechanism + evidence level when available.
2. **Inform, don't decide** — interventions with contraindications remain visible, ranked lower with prominent warnings.
3. **Modular graph** — new medications, conditions, and peptides are new nodes/edges, not pipeline changes.
4. **Separated from reasoning** — safety logic lives in `app/safety_engine/`, not in the LLM reasoner.

## Inputs

| Source | Fields |
|--------|--------|
| Health profile | age, sex, medications, supplements, conditions |
| Labs (optional) | eGFR, Creatinine, AST, ALT, GGT |
| Reasoning output | candidate `LLMRecommendation` list |

## Outputs (per intervention)

- `safety_rating`: low / moderate / high / contraindicated
- `warnings[]`: typed entries (interaction, contraindication, organ_caution, pregnancy_lactation)
- `contraindications[]`, `organ_cautions[]`, `pregnancy_lactation_warnings[]`
- `requires_prominent_warning`: drives UI highlight + ranking deprioritization

## Graph model

### Node types (`SafetyNodeType`)

`medication`, `supplement`, `botanical`, `food_compound`, `peptide`, `lifestyle`, `condition`, `organ_system`, `intervention`

### Relationship types (`SafetyRelationshipType`)

| Type | Example |
|------|---------|
| `interacts_with` | Curcumin ↔ Warfarin |
| `contraindicated_in` | Berberine ↔ pregnancy |
| `use_with_caution` | Curcumin ↔ pregnancy |
| `caution_in` | EGCG ↔ liver disease |
| `affects_pathway` | (reserved) |

### MVP coverage

- **~44 medications** in `app/safety_engine/medication_catalog.py`
- **10 condition categories** in `app/safety_engine/condition_catalog.py`
- **30+ seeded edges** in `app/safety_engine/graph_seed.py`
- Legacy herb–drug pairs bridged from `app/safety_engine/legacy_data.py`

## Ranking behavior

Confidence scores are adjusted with `adjusted_confidence()`:

- Moderate safety concern: −15% effective confidence
- High: −35%
- Contraindicated: −55%

Recommendations with `requires_prominent_warning` sort after safer options.

## API (`/api/v1/safety`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/medications` | MVP medication catalog |
| GET | `/conditions` | Condition categories |
| GET | `/graph/edges` | Seeded safety relationships |
| GET | `/interventions/{name}` | Static safety profile |
| POST | `/evaluate` | Dry-run with patient context |

## Database

Alembic migration `c3d4e5f6a7b8` adds:

- `safety_graph_nodes`
- `safety_graph_edges`

Runtime evaluation uses in-memory seed data today; DB tables support future admin tooling and external curation.

## Non-goals (v1.0)

- Prescribing or dosing directives
- Autonomous treatment plans
- Removing interventions solely for theoretical interactions
- Full drug–drug interaction database (scope: common outpatient meds only)

## Extension guide

1. Add medication to `medication_catalog.py`
2. Add edge to `graph_seed.py` (or DB via future seeder)
3. Add pytest in `tests/test_safety_engine/`
4. No changes to LLM reasoner required