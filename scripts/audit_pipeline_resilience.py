#!/usr/bin/env python3
"""CI gate: full scenario matrix + adversarial mutations must not crash the pipeline.

Catches regressions across biomarkers, pathways, infectious disease formats,
OCR garbling, and PDF column-bleed tricks — the things that blow up in production
but pass isolated unit tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.pipeline.adversarial_formats import MUTATION_IDS  # noqa: E402
from app.pipeline.pipeline_resilience import probe_all_scenarios  # noqa: E402

# Representative scenarios per recommendation tree — must complete worker + report path in pytest.
CRITICAL_TREE_SCENARIOS = frozenset({
    "signaling_inflammatory_quest",
    "etiological_h_pylori_urea_breath",
    "exposure_h_pylori_igg",
    "culture_urine_positive",
    "culture_sputum_positive",
    "etiological_hepatitis_b_surf_positive",
    "celiac_ttg_iga_positive",
    "allergy_peanut_ige_high",
    "pgx_cyp2d6_intermediate",
    "autoimmune_ana_positive",
    "nutritional_macrocytic_cbc",
    "niche_fecal_calprotectin_elevated",
    "format_healow_lipid_panel",
    "format_ocr_garbled_cbc",
    "kitchen_sink_quest_excerpt",
})


def main() -> int:
    probes_per = 1 + len(MUTATION_IDS)
    results = probe_all_scenarios(skip_ci=True, include_mutations=True)

    crashes = [r for r in results if not r.passed]
    unresolved = [r for r in results if r.unresolved_abnormals and r.probe_id.endswith(":base")]

    print(f"=== Pipeline resilience ({len(results)} probes = 75 scenarios × {probes_per}) ===")
    print(f"Crashes: {len(crashes)}")
    print(f"Base scenarios with unresolved abnormals: {len(unresolved)}")
    print(f"Critical tree scenarios (E2E in pytest): {len(CRITICAL_TREE_SCENARIOS)}")

    failed = 0
    if crashes:
        failed += len(crashes)
        print("\nCRASHES:")
        for r in crashes[:20]:
            print(f"  {r.probe_id}: {r.error}")
        if len(crashes) > 20:
            print(f"  ... and {len(crashes) - 20} more")

    if unresolved:
        failed += len(unresolved)
        print("\nUNRESOLVED ABNORMALS (base probes):")
        for r in unresolved[:15]:
            print(f"  {r.probe_id}: {r.unresolved_abnormals}")

    if failed:
        print(f"\nFAIL: {failed} probe failure(s)")
        return 1

    print("\nAll probes passed — no pipeline crashes or unresolved catalog abnormals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())