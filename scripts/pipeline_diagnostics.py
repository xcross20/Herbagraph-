#!/usr/bin/env python3
"""Stage-by-stage pipeline diagnostics for lab files and samples.

Usage:
  python scripts/pipeline_diagnostics.py
  python scripts/pipeline_diagnostics.py path/to/lab.pdf
  python scripts/pipeline_diagnostics.py --lab-report-id <uuid>   # requires DB + .env
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _header(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def diagnose_bytes(file_bytes: bytes, filename: str) -> int:
    from app.pipeline.biomarker_normalizer import get_reference_data, normalize_lab_results
    from app.pipeline.lab_parser import extract_text_from_pdf, parse_lab_file, parse_lab_text
    from app.pipeline.pathway_mapper import map_pathways

    _header(f"Stage 0: Input — {filename} ({len(file_bytes)} bytes)")

    if filename.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
        _header("Stage 1a: PDF text extraction")
        print(f"  extracted_chars={len(text)}  lines={len(text.splitlines())}")
        if text.strip():
            print("  first_line:", repr(text.splitlines()[0][:100]))
        parsed = parse_lab_text(text)
    else:
        text = file_bytes.decode("utf-8", errors="replace")
        parsed = parse_lab_file(file_bytes, filename)

    _header("Stage 1b: Line parsing")
    print(f"  parsed_rows={len(parsed)}")
    for row in parsed[:15]:
        print(f"    - {row.raw_test_name}: {row.value} {row.unit or ''} ({row.reference_range_low}-{row.reference_range_high})")
    if len(parsed) > 15:
        print(f"    ... +{len(parsed) - 15} more")

    _header("Stage 2: Biomarker normalization")
    normalized = normalize_lab_results(parsed)
    tracked = [n for n in normalized if get_reference_data(n.biomarker_name)]
    print(f"  normalized_rows={len(normalized)}  tracked_mvp_biomarkers={len(tracked)}")
    for row in tracked:
        print(f"    - {row.biomarker_name}: {row.value} -> {row.status.value}")

    _header("Stage 3: Pathway mapping (dry run)")
    pathways = map_pathways(normalized)
    active = [p for p in pathways if p.activation_score > 0]
    print(f"  pathways_mapped={len(pathways)}  active={len(active)}")
    for p in active[:10]:
        print(f"    - {p.pathway_code}: score={p.activation_score:.2f} direction={p.direction.value}")

    if not parsed:
        print("\nRESULT: FAIL — no biomarker rows parsed")
        return 1
    if not tracked:
        print("\nRESULT: WARN — parsed rows exist but none map to MVP biomarker panel")
        return 0
    print("\nRESULT: PASS")
    return 0


def diagnose_lab_report_id(lab_report_id: str) -> int:
    from sqlalchemy import create_engine, text

    from app.config import settings
    from app.core.file_storage import load_lab_file
    from app.database import _to_sync_url

    engine = create_engine(_to_sync_url(settings.database_url))
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT original_filename, encrypted_file_path FROM lab_reports WHERE id = :id"),
            {"id": lab_report_id},
        ).mappings().first()
    if row is None:
        print(f"No lab report found: {lab_report_id}")
        return 1
    file_bytes = load_lab_file(row["encrypted_file_path"])
    return diagnose_bytes(file_bytes, row["original_filename"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HerbaGraph pipeline stage diagnostics")
    parser.add_argument("path", nargs="?", help="Lab file (.pdf, .txt, .csv)")
    parser.add_argument("--lab-report-id", help="Diagnose a persisted lab report by UUID")
    args = parser.parse_args()

    failures = 0

    if args.lab_report_id:
        failures += diagnose_lab_report_id(args.lab_report_id)
        return failures

    targets: list[Path] = []
    if args.path:
        targets.append(Path(args.path))
    else:
        samples = ROOT / "samples" / "lab_reports"
        if samples.exists():
            targets.extend(sorted(samples.glob("*.*")))
        fixture = ROOT / "tests" / "fixtures" / "quest_labreport_excerpt.txt"
        if fixture.exists():
            targets.append(fixture)

    if not targets:
        print("No files to diagnose. Pass a path or add samples under samples/lab_reports/")
        return 1

    for path in targets:
        if path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() not in {".pdf", ".txt", ".csv"}:
            continue
        failures += diagnose_bytes(path.read_bytes(), path.name)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())