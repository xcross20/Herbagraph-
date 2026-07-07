#!/usr/bin/env python3
"""Validate lab scenario matrix (parse → normalize → route).

Run from repo root:
  python scripts/validate_lab_scenarios.py
  python scripts/validate_lab_scenarios.py --include-skip-ci
  python scripts/validate_lab_scenarios.py --scenario etiological_h_pylori_urea_breath
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pipeline.lab_scenario_loader import (  # noqa: E402
    list_scenarios,
    load_manifest,
    validate_all_scenarios,
    validate_scenario,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate samples/lab_scenarios/manifest.json")
    parser.add_argument("--scenario", help="Validate a single scenario_id")
    parser.add_argument(
        "--include-skip-ci",
        action="store_true",
        help="Include scenarios marked skip_ci (e.g. LLM fallback manual QA)",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Override manifest path")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest) if args.manifest else load_manifest()

    if args.scenario:
        scenario = next((s for s in list_scenarios(manifest) if s["scenario_id"] == args.scenario), None)
        if scenario is None:
            print(f"Unknown scenario: {args.scenario}")
            return 1
        results = [validate_scenario(scenario)]
    else:
        results = validate_all_scenarios(manifest, skip_ci=not args.include_skip_ci)

    failed = 0
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        extra = f" parsed={result.parsed_count} abnormal={result.abnormal_count}"
        if result.primary_tree:
            extra += f" primary={result.primary_tree}"
        print(f"  [{status}] {result.scenario_id}{extra}")
        for warning in result.warnings:
            print(f"         warn: {warning}")
        for error in result.errors:
            print(f"         error: {error}")
        if not result.passed:
            failed += 1

    print(f"\nValidated {len(results)} scenario(s); {len(results) - failed} passed, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())