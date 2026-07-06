#!/usr/bin/env python3
"""Verify all files in samples/lab_reports/ parse through Stage 1 + 2."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "lab_reports"


def main() -> int:
    from app.pipeline.biomarker_normalizer import get_reference_data, normalize_lab_results
    from app.pipeline.lab_parser import parse_lab_file

    if not SAMPLES.exists():
        print(f"No samples dir: {SAMPLES}")
        return 1

    files = sorted(
        p for p in SAMPLES.iterdir()
        if p.suffix.lower() in {".txt", ".csv", ".pdf"} and p.name != "README.md"
    )
    if not files:
        print("No sample files found")
        return 1

    failed = 0
    for path in files:
        raw = path.read_bytes()
        parsed = parse_lab_file(raw, path.name)
        normalized = normalize_lab_results(parsed)
        tracked = [n for n in normalized if get_reference_data(n.biomarker_name)]
        print(
            f"  {path.name:40s} parsed={len(parsed):2d}  "
            f"normalized={len(normalized):2d}  tracked={len(tracked):2d}"
        )
        if len(parsed) < 3:
            print(f"    WARN: fewer than 3 parsed rows")
            failed += 1

    print(f"\nChecked {len(files)} file(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())