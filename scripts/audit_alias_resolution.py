#!/usr/bin/env python3
"""Fuzz-test lab naming variants resolve to catalog canonical biomarkers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge_graph.biomarker_catalog import BIOMARKER_ENTRIES, REFERENCE_DATA
from app.pipeline.user_biomarker_profile import resolve_canonical_name

# Real Quest/LabCorp naming patterns (parenthetical abbrev, mean-cell CBC wording).
_CURATED_LAB_PATTERNS: list[tuple[str, str]] = [
    ("MCH", "Mean Cell Hemoglobin (MCH)"),
    ("MCV", "Mean Cell Volume (MCV)"),
    ("RDW", "Red Cell Distribution Width (RDW)"),
    ("WBC", "White Blood Cell (WBC)"),
    ("RBC", "Red Blood Cell (RBC)"),
    ("CRP", "C-Reactive Protein"),
    ("CRP", "High Sensitivity CRP"),
    ("Glucose", "Glucose, Serum"),
    ("Glucose", "Fasting Glucose"),
    ("LDL", "LDL Cholesterol Calc"),
    ("HDL", "HDL Cholesterol"),
    ("B12", "Vitamin B12"),
    ("TSH", "Thyroid Stimulating Hormone"),
    ("Ferritin", "Ferritin, Serum"),
    ("Vitamin D", "Vitamin D, 25-Hydroxy"),
    ("Vitamin D", "Vitamin D, 25-OH"),
    ("Vitamin D", "Vit D 25-Hydroxy"),
    ("Iron", "Iron, Total"),
    ("B12", "Vitamin B-12"),
    ("Folate", "Folate (Folic Acid), Serum"),
    ("Homocysteine", "Homocysteine, Plasma"),
    ("Methylmalonic Acid", "Methylmalonic Acid, Serum"),
    ("Zinc", "Zinc, Plasma"),
    ("Copper", "Copper, Serum"),
    ("Selenium", "Selenium, Serum"),
    ("Magnesium", "Magnesium, RBC"),
    ("Transferrin Saturation", "% Saturation"),
    ("TIBC", "Iron Binding Capacity"),
    ("UIBC", "Unsaturated Iron Binding Capacity"),
    ("Vitamin A", "Vitamin A, Serum"),
    ("Vitamin E", "Vitamin E, Serum"),
    ("Vitamin K", "Vitamin K, Plasma"),
    ("Vitamin B1", "Thiamine, Plasma"),
    ("Vitamin B2", "Riboflavin, Plasma"),
    ("Vitamin B6", "Pyridoxine, Plasma"),
    ("Vitamin C", "Vitamin C, Plasma"),
    ("Prealbumin", "Prealbumin, Serum"),
    ("MCV", "emuloV lleC naeM (MCV)"),
    ("MCH", "nibolgomeH lleC naeM (MCH)"),
    ("CRP", "CRP (calc)"),
    ("Glucose", "glucose calc"),
    ("LDL", "LDL Cholesterol Calc"),
]


def _catalog_alias_rows() -> list[tuple[str, str, str]]:
    """Every catalog alias must resolve (hard gate)."""
    rows: list[tuple[str, str, str]] = []
    for entry in BIOMARKER_ENTRIES:
        canonical = entry["canonical_name"]
        for alias in entry.get("aliases", []):
            rows.append((canonical, alias, alias))
    return rows


def _format_variant_rows() -> list[tuple[str, str, str]]:
    """Title/upper-case and curated lab-portal strings (100+ variants)."""
    rows: list[tuple[str, str, str]] = []
    for entry in BIOMARKER_ENTRIES:
        canonical = entry["canonical_name"]
        aliases = entry.get("aliases", [])
        seen: set[str] = set()
        for alias in aliases[:4]:
            for variant in (alias, alias.title(), alias.upper()):
                key = variant.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append((canonical, alias, variant))
    for canonical, variant in _CURATED_LAB_PATTERNS:
        rows.append((canonical, variant, variant))
    return rows


def _audit(rows: list[tuple[str, str, str]], label: str) -> list[tuple[str, str, str]]:
    failures: list[tuple[str, str, str]] = []
    for canonical, _source, variant in rows:
        resolved = resolve_canonical_name(variant)
        if resolved != canonical:
            failures.append((canonical, variant, resolved or "<unresolved>"))
    print(f"{label}: tested {len(rows)}, failures {len(failures)}")
    return failures


def main() -> int:
    alias_failures = _audit(_catalog_alias_rows(), "Catalog aliases")
    variant_failures = _audit(_format_variant_rows(), "Format variants")

    print(f"Catalog biomarkers: {len(REFERENCE_DATA)}")
    all_failures = alias_failures + variant_failures
    if all_failures:
        for canonical, variant, got in all_failures[:40]:
            print(f"  {canonical!r}: {variant!r} -> {got}")
        if len(all_failures) > 40:
            print(f"  ... and {len(all_failures) - 40} more")
        print("\nSuggested supplemental aliases:")
        seen: set[str] = set()
        for canonical, variant, _ in all_failures:
            key = (canonical, variant.lower())
            if key in seen:
                continue
            seen.add(key)
            print(f'  "{variant.lower()}": "{canonical}",')
        return 1

    print("All alias checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())