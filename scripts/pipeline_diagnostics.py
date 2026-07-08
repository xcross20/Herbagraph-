#!/usr/bin/env python3
"""One-command HerbaGraph pipeline health report for operators."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def main() -> int:
    print("=== HerbaGraph Pipeline Diagnostics ===\n")

    from app.knowledge_graph.biomarker_catalog import REFERENCE_DATA
    from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS, INTERVENTIONS
    from app.pipeline.lab_scenario_loader import load_manifest, validate_all_scenarios

    print(f"Biomarker catalog: {len(REFERENCE_DATA)} tests")
    print(f"Interventions (seed): {len(INTERVENTIONS)}")
    print(f"Evidence claims (seed): {len(EVIDENCE_CLAIMS)}")

    checks = [
        ("Seed catalog counts", [sys.executable, "scripts/validate_seed_counts.py"]),
        ("Pathway coverage", [sys.executable, "scripts/validate_pathway_coverage.py"]),
        ("Alias resolution", [sys.executable, "scripts/audit_alias_resolution.py"]),
        ("Evidence gaps (priority pathways)", [sys.executable, "scripts/audit_evidence_gaps.py"]),
        ("Lab scenarios", [sys.executable, "scripts/validate_lab_scenarios.py"]),
        ("PMID integrity (denylist)", [sys.executable, "scripts/audit_pmid_integrity.py"]),
        ("Sample lab parse", [sys.executable, "scripts/validate_sample_labs.py"]),
        ("Scenario coverage", [sys.executable, "scripts/audit_scenario_coverage.py"]),
        ("Unresolved abnormals", [sys.executable, "scripts/audit_unresolved_abnormals.py"]),
        ("Pipeline resilience", [sys.executable, "scripts/audit_pipeline_resilience.py"]),
    ]

    failed = 0
    for label, cmd in checks:
        code, output = _run(cmd)
        status = "PASS" if code == 0 else "FAIL"
        print(f"\n[{status}] {label}")
        if output:
            for line in output.splitlines()[-6:]:
                print(f"  {line}")
        if code != 0:
            failed += 1

    manifest = load_manifest()
    scenarios = [s for s in manifest["scenarios"] if not s.get("skip_ci")]
    with_recs = sum(
        1 for s in scenarios if s.get("expect", {}).get("recommendations", {}).get("must_include")
    )
    with_pathways = sum(
        1 for s in scenarios if s.get("expect", {}).get("pathways", {}).get("must_include")
    )
    with_systems = sum(
        1 for s in scenarios if s.get("expect", {}).get("biological_systems", {}).get("must_include")
    )
    results = validate_all_scenarios(manifest, skip_ci=True)
    passed = sum(1 for r in results if r.passed)

    print(f"\nLab scenario matrix: {passed}/{len(results)} passed")
    print(f"Scenarios with pathway asserts: {with_pathways}")
    print(f"Scenarios with recommendation asserts: {with_recs}")
    print(f"Scenarios with biological_systems asserts: {with_systems}")

    if failed:
        print(f"\nDiagnostics: {failed} gate(s) failed.")
        return 1

    print("\nDiagnostics: all gates green.")

    reseed_code, reseed_out = _run(["bash", "scripts/ops_reseed.sh"])
    print(f"\n[{'PASS' if reseed_code == 0 else 'FAIL'}] Ops reseed")
    if reseed_out:
        for line in reseed_out.splitlines()[-4:]:
            print(f"  {line}")
    return reseed_code if reseed_code != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())