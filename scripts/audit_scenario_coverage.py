#!/usr/bin/env python3
"""Report lab scenario matrix assertion coverage (pathways, biological_systems, recommendations)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.lab_scenario_loader import list_scenarios, load_manifest

MIN_RECOMMENDATION_SCENARIOS = 70
MIN_PATHWAY_SCENARIOS = 70
MIN_BIOLOGICAL_SYSTEMS_SCENARIOS = 70


def main() -> int:
    manifest = load_manifest()
    scenarios = [s for s in list_scenarios(manifest) if not s.get("skip_ci")]

    with_pathways = 0
    with_systems = 0
    with_recs = 0
    gaps: list[str] = []

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        expect = scenario.get("expect", {})
        has_pathways = bool(expect.get("pathways", {}).get("must_include"))
        has_systems = bool(expect.get("biological_systems", {}).get("must_include"))
        has_recs = bool(expect.get("recommendations", {}).get("must_include"))

        if has_pathways:
            with_pathways += 1
        if has_systems:
            with_systems += 1
        if has_recs:
            with_recs += 1

        max_abnormal = expect.get("routing", {}).get("max_abnormal", 99)
        is_negative_control = bool(expect.get("negative_control")) or max_abnormal == 0

        missing = []
        if not has_recs and not is_negative_control:
            missing.append("recommendations")
        if not has_pathways and not is_negative_control:
            missing.append("pathways")
        if not has_systems and not expect.get("biological_systems_skip") and not is_negative_control:
            missing.append("biological_systems")
        if missing:
            gaps.append(f"  {sid}: missing {', '.join(missing)}")

    total = len(scenarios)
    print(f"CI scenarios: {total}")
    print(f"With pathway asserts: {with_pathways}")
    print(f"With biological_systems asserts: {with_systems}")
    print(f"With recommendation asserts: {with_recs}")

    failed = False
    if with_recs < MIN_RECOMMENDATION_SCENARIOS:
        print(f"\nFAIL: expected >= {MIN_RECOMMENDATION_SCENARIOS} scenarios with recommendations")
        failed = True
    if with_pathways < MIN_PATHWAY_SCENARIOS:
        print(f"FAIL: expected >= {MIN_PATHWAY_SCENARIOS} scenarios with pathways")
        failed = True
    if with_systems < MIN_BIOLOGICAL_SYSTEMS_SCENARIOS:
        print(f"FAIL: expected >= {MIN_BIOLOGICAL_SYSTEMS_SCENARIOS} scenarios with biological_systems")
        failed = True

    if gaps:
        print("\nScenarios with assertion gaps:")
        for line in gaps[:15]:
            print(line)
        if len(gaps) > 15:
            print(f"  ... and {len(gaps) - 15} more")

    if failed:
        return 1

    print("\nScenario matrix coverage thresholds met.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())