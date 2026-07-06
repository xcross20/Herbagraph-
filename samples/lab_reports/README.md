# Demo Lab Reports

Synthetic lab files for HerbaGraph demos. **Not real patient data.**

## Quick demo (UI)

1. Start the app: `docker compose up -d`
2. Open http://localhost:8000/
3. Upload **`demo_01_inflammatory_quest.txt`** or **`demo_03_comprehensive_quest.txt`**
4. Click **Analyze** and wait for the report (~1–3 min)

## Files

| File | Style | Best for |
|------|-------|----------|
| `demo_01_inflammatory_quest.txt` | Quest | Fast demo — elevated CRP + metabolic flags |
| `demo_02_metabolic_labcorp.txt` | LabCorp | H/L flags, metabolic + liver markers |
| `demo_03_comprehensive_quest.txt` | Quest | Full ~25-biomarker MVP panel |
| `demo_04_followup_improved.txt` | Quest | Response-tracking follow-up (use after demo_01/03) |
| `demo_05_mixed_panel.csv` | CSV | Table upload format |
| `demo_06_pipe_delimited.txt` | Pipe | Alternate parser format |

## Response tracking demo

1. Upload `demo_01_inflammatory_quest.txt` → wait for report
2. Upload `demo_04_followup_improved.txt` → create tracking record via API
3. Compare baseline vs follow-up CRP and inflammation system

## Validate samples parse

```bash
python scripts/validate_sample_labs.py
```