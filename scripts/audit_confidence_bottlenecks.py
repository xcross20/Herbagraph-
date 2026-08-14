#!/usr/bin/env python3
"""Classify why catalog-only recommendations sit below High.

Runs CI lab scenarios through the existing lab engine + decomposition.
Prints bottleneck histogram. Does not invent PMIDs or change scores.

  python3 scripts/audit_confidence_bottlenecks.py
  python3 scripts/audit_confidence_bottlenecks.py --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.evidence_confidence.engine import explain_recommendation  # noqa: E402
from app.pipeline.catalog_evidence import (  # noqa: E402
    build_catalog_evidence_snippets,
    build_catalog_reasoning_output,
)
from app.pipeline.intervention_catalog import build_interventions_for_routing  # noqa: E402
from app.pipeline.lab_scenario_loader import (  # noqa: E402
    list_scenarios,
    load_manifest,
    resolve_raw_path,
)
from app.pipeline.lab_parser import parse_lab_file  # noqa: E402
from app.pipeline.biomarker_normalizer import normalize_lab_results  # noqa: E402
from app.pipeline.pathway_mapper import map_pathways  # noqa: E402
from app.pipeline.test_type_router import route_recommendation_trees  # noqa: E402


def _run_scenario(raw_path: Path) -> list[dict]:
    parsed = parse_lab_file(raw_path.read_bytes(), raw_path.name)
    normalized = normalize_lab_results(parsed)
    abnormal = [n for n in normalized if n.status.value in ("critical_low", "low", "high", "critical_high")]
    if not abnormal:
        return []
    pathways = map_pathways(normalized)
    routing = route_recommendation_trees(normalized, pathways)
    routed = build_interventions_for_routing(routing, pathways, normalized)
    names = {name for group in routed.values() for name in group}
    if not names:
        return []
    snippets = build_catalog_evidence_snippets(
        names,
        abnormal_biomarkers={n.biomarker_name for n in abnormal},
        pathway_codes={p.pathway_code for p in pathways},
        routing=routing,
    )
    reasoning = build_catalog_reasoning_output(
        snippets,
        abnormal_biomarkers={n.biomarker_name for n in abnormal},
        pathway_activations=pathways,
        routing=routing,
    )
    intervention_pathways: dict[str, list[str]] = {}
    for rec in reasoning.recommendations:
        intervention_pathways[rec.intervention_name] = [p.pathway_code for p in pathways]
    rows = []
    for rec in reasoning.recommendations:
        explained = explain_recommendation(
            rec,
            snippets,
            pathways,
            intervention_pathways,
            normalized,
            {},
        )
        decomp = explained.confidence_decomposition
        if decomp is None:
            continue
        rows.append(
            {
                "intervention": rec.intervention_name,
                "evidence": decomp.evidence_confidence.percent,
                "patient_match": decomp.patient_match.percent,
                "sufficiency": decomp.data_sufficiency.percent,
                "decision": decomp.decision_confidence.percent,
                "band": decomp.decision_band,
                "bottleneck": decomp.primary_bottleneck,
                "missing_markers": decomp.missing_biomarkers[:5],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Max CI scenarios (0 = all)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    scenarios = [s for s in list_scenarios(load_manifest()) if s.get("ci", True)]
    if args.limit:
        scenarios = scenarios[: args.limit]

    bottleneck = Counter()
    bands = Counter()
    all_rows: list[dict] = []
    for scenario in scenarios:
        raw = resolve_raw_path(scenario)
        try:
            rows = _run_scenario(raw)
        except Exception as exc:  # noqa: BLE001 — audit must continue
            print(f"skip {scenario.get('scenario_id')}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        for row in rows:
            row["scenario_id"] = scenario.get("scenario_id")
            bottleneck[row["bottleneck"]] += 1
            bands[row["band"]] += 1
            all_rows.append(row)

    total = sum(bottleneck.values()) or 1
    summary = {
        "recommendations": len(all_rows),
        "scenarios": len(scenarios),
        "bottleneck_pct": {k: round(100 * v / total, 1) for k, v in bottleneck.most_common()},
        "decision_bands": dict(bands),
    }
    if args.json:
        print(json.dumps({"summary": summary, "rows": all_rows}, indent=2))
        return 0

    print(f"Recommendations scored: {len(all_rows)} across {len(scenarios)} scenarios")
    print("Primary bottleneck:")
    for key, pct in summary["bottleneck_pct"].items():
        print(f"  {key:28} {pct}%")
    print("Decision bands:", dict(bands))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
