#!/usr/bin/env python3
"""CI gate: every abnormal biomarker in scenarios + blindspot fixtures must be in catalog.

Catches the exact UI failure mode: abnormal rows with in_catalog=false and no pathways/recs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pipeline.biomarker_normalizer import normalize_lab_results  # noqa: E402
from app.pipeline.lab_parser import parse_lab_file  # noqa: E402
from app.pipeline.lab_scenario_loader import list_scenarios, load_manifest, resolve_raw_path  # noqa: E402
from app.pipeline.user_biomarker_profile import is_catalog_biomarker  # noqa: E402

_ABNORMAL = frozenset({"critical_low", "low", "high", "critical_high"})

BLINDSPOT_FIXTURES = (
    ROOT / "tests" / "fixtures" / "healow_lipid_panel_excerpt.txt",
    ROOT / "samples" / "lab_scenarios" / "raw" / "format_quest_hdl_ldl_flags.txt",
)


def _unresolved_abnormals(raw: bytes, filename: str, custom_biomarkers: list | None = None) -> list[str]:
    parsed = parse_lab_file(raw, filename)
    normalized = normalize_lab_results(parsed, custom_biomarkers=custom_biomarkers)
    return [
        lab.biomarker_name
        for lab in normalized
        if lab.status.value in _ABNORMAL and not is_catalog_biomarker(lab.biomarker_name)
    ]


def main() -> int:
    failed = 0

    manifest = load_manifest()
    scenarios = [s for s in list_scenarios(manifest) if not s.get("skip_ci")]

    catalog_scenarios = [s for s in scenarios if not s.get("custom_biomarkers")]
    print(f"=== Unresolved abnormal audit ({len(catalog_scenarios)} catalog CI scenarios) ===")
    for scenario in catalog_scenarios:
        path = resolve_raw_path(scenario)
        unresolved = _unresolved_abnormals(path.read_bytes(), path.name)
        if unresolved:
            failed += 1
            print(f"  FAIL {scenario['scenario_id']}: {unresolved}")

    print(f"\n=== Blindspot fixtures ({len(BLINDSPOT_FIXTURES)}) ===")
    for path in BLINDSPOT_FIXTURES:
        if not path.exists():
            print(f"  FAIL missing fixture: {path}")
            failed += 1
            continue
        unresolved = _unresolved_abnormals(path.read_bytes(), path.name)
        if unresolved:
            failed += 1
            print(f"  FAIL {path.name}: {unresolved}")
        else:
            print(f"  OK   {path.name}")

    if failed:
        print(f"\nFAIL: {failed} source(s) have abnormal biomarkers outside catalog")
        return 1

    print("\nAll abnormal biomarkers resolve to catalog")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())