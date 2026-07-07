# Lab Scenario Matrix

Master payload for validating HerbaGraph lab parsing, normalization, and test-type routing.

**Not real patient data** — all `raw/` files are synthetic except `kitchen_sink_quest_excerpt`, which references a de-identified Quest PDF text export in `tests/fixtures/`.

## Quick validate

```bash
python scripts/validate_lab_scenarios.py
pytest tests/test_lab_scenarios/ -q
```

## Structure

| Path | Purpose |
|------|---------|
| `manifest.json` | Scenario definitions + expectations |
| `raw/*.txt` | Focused synthetic lab files (one primary intent each) |
| `../lab_reports/demo_*.txt` | Reused format/routing demos |
| `../../tests/fixtures/quest_labreport_excerpt.txt` | Kitchen-sink parser stress test |

## Scenario matrix (18)

| ID | Primary tree | What it exercises |
|----|--------------|-------------------|
| `signaling_inflammatory_quest` | signaling | Quest paren, CRP/metabolic/lipids |
| `signaling_labcorp_hl_flags` | signaling | LabCorp H/L flags |
| `signaling_comprehensive_quest` | nutritional_repletion | Full MVP panel + low Vitamin D |
| `format_csv_mixed_panel` | signaling | CSV upload |
| `format_pipe_delimited` | signaling | Pipe-delimited |
| `format_quest_hdl_ldl_flags` | signaling | HDL `L` + LDL `NEAR OPTIMAL` |
| `etiological_h_pylori_urea_breath` | etiological | Active H. pylori → Mastic Gum path |
| `exposure_h_pylori_igg` | exposure | Prior exposure serology |
| `culture_urine_positive` | etiological | Positive urine culture |
| `culture_urine_no_growth` | signaling | Negative control (no abnormal) |
| `celiac_ttg_iga_positive` | celiac | tTG IgA POSITIVE |
| `allergy_peanut_ige_high` | allergy | Peanut + Total IgE |
| `pgx_cyp2d6_intermediate` | pgx_context | CYP2D6 genotype line |
| `autoimmune_ana_positive` | autoimmune | Elevated ANA |
| `nutritional_vitd_low` | nutritional_repletion | Isolated low Vitamin D |
| `custom_unknown_biomarker` | signaling | Custom `Lp(a) Mass` profile entry |
| `trend_followup_improved` | — | Paired with inflammatory baseline |
| `kitchen_sink_quest_excerpt` | etiological | 56-row real Quest export |
| `llm_fallback_messy` | — | Manual LLM QA (`skip_ci`) |

## UI manual QA

1. Upload `raw/etiological_h_pylori_urea_breath.txt` → expect Mastic Gum / DGL in report.
2. Upload `raw/pgx_cyp2d6_intermediate.txt` → medication context only, not directives.
3. Upload baseline `signaling_inflammatory_quest.txt`, then `../lab_reports/demo_04_followup_improved.txt` for trends.

## Adding a scenario

1. Add `raw/your_scenario.txt`
2. Add entry to `manifest.json` with `expect.parse`, `expect.normalize`, `expect.routing`
3. Run `python scripts/validate_lab_scenarios.py --scenario your_scenario_id`