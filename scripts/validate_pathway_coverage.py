#!/usr/bin/env python3
"""Fail if any catalog biomarker lacks pathway mapping rules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge_graph.biomarker_catalog import REFERENCE_DATA
from app.pipeline.pathway_mapper import _PATHWAY_CONFIGS, get_pathways_for_biomarker


def main() -> int:
    missing = [name for name in sorted(REFERENCE_DATA) if not get_pathways_for_biomarker(name)]
    print(f"Catalog biomarkers: {len(REFERENCE_DATA)}")
    print(f"Pathway rules: {len(_PATHWAY_CONFIGS)}")
    print(f"Biomarkers with pathways: {len(REFERENCE_DATA) - len(missing)}")
    if missing:
        print("Missing pathway coverage:")
        for name in missing:
            print(f"  - {name} ({REFERENCE_DATA[name]['category']})")
        return 1
    print("All catalog biomarkers have pathway mappings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())