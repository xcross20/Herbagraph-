"""Merge multiple parsed lab reports into one integrated biomarker snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.pipeline.biomarker_normalizer import normalized_result_from_lab_result
from app.pipeline.user_biomarker_profile import is_catalog_biomarker
from app.schemas.pipeline import NormalizedLabResult


def infer_panel_label(filename: str) -> str:
    lower = (filename or "").lower()
    hints = [
        ("cbc", "CBC"),
        ("cmp", "CMP"),
        ("comprehensive metabolic", "CMP"),
        ("lipid", "Lipid Panel"),
        ("ferritin", "Iron Panel"),
        ("iron", "Iron Panel"),
        ("vitamin d", "Vitamin D Panel"),
        ("thyroid", "Thyroid Panel"),
        ("tsh", "Thyroid Panel"),
        ("hba1c", "HbA1c"),
        ("crp", "Inflammatory Panel"),
    ]
    for token, label in hints:
        if token in lower:
            return label
    stem = filename.rsplit(".", 1)[0] if filename else "Lab Report"
    return stem[:80] or "Lab Report"


def _parse_confidence(normalized: NormalizedLabResult) -> float:
    if is_catalog_biomarker(normalized.biomarker_name):
        return 1.0
    if normalized.category:
        return 0.85
    return 0.7


def _same_day(a: datetime | None, b: datetime | None) -> bool:
    if a is None or b is None:
        return False
    return a.date() == b.date()


@dataclass
class MergeCandidate:
    normalized: NormalizedLabResult
    source_lab_report_id: str
    collected_at: datetime | None
    confidence: float
    panel_label: str
    filename: str


@dataclass
class IntegratedMergeResult:
    snapshot: list[NormalizedLabResult]
    integrated_rows: list[dict]
    sources: list[dict]
    conflicts: list[dict] = field(default_factory=list)


def merge_lab_reports(
    lab_reports: list,
    *,
    panel_labels: dict[str, str] | None = None,
    custom_biomarkers: list[dict] | None = None,
) -> IntegratedMergeResult:
    """Apply duplicate/conflict rules and return the current integrated snapshot."""
    panel_labels = panel_labels or {}
    candidates_by_biomarker: dict[str, list[MergeCandidate]] = {}

    sources: list[dict] = []
    for report in lab_reports:
        label = panel_labels.get(str(report.id)) or infer_panel_label(report.original_filename)
        collected = report.created_at
        if collected and collected.tzinfo is None:
            collected = collected.replace(tzinfo=timezone.utc)
        sources.append(
            {
                "lab_report_id": str(report.id),
                "filename": report.original_filename,
                "panel_label": label,
                "collected_at": collected.isoformat() if collected else None,
                "biomarker_count": len(report.lab_results or []),
            }
        )
        for row in report.lab_results or []:
            normalized = normalized_result_from_lab_result(row, custom_biomarkers=custom_biomarkers)
            candidate = MergeCandidate(
                normalized=normalized,
                source_lab_report_id=str(report.id),
                collected_at=collected,
                confidence=_parse_confidence(normalized),
                panel_label=label,
                filename=report.original_filename,
            )
            candidates_by_biomarker.setdefault(normalized.biomarker_name, []).append(candidate)

    snapshot: list[NormalizedLabResult] = []
    integrated_rows: list[dict] = []
    conflicts: list[dict] = []

    for biomarker_name, entries in sorted(candidates_by_biomarker.items()):
        entries_sorted = sorted(
            entries,
            key=lambda e: (
                e.collected_at or datetime.min.replace(tzinfo=timezone.utc),
                e.confidence,
            ),
            reverse=True,
        )
        by_day: dict[str, list[MergeCandidate]] = {}
        for entry in entries_sorted:
            day_key = (entry.collected_at.date().isoformat() if entry.collected_at else "unknown")
            by_day.setdefault(day_key, []).append(entry)

        chosen: MergeCandidate | None = None
        for day_entries in by_day.values():
            day_entries.sort(key=lambda e: e.confidence, reverse=True)
            top = day_entries[0]
            if len(day_entries) > 1 and abs(day_entries[0].normalized.value - day_entries[1].normalized.value) > 1e-6:
                conflicts.append(
                    {
                        "biomarker_name": biomarker_name,
                        "values": [
                            {
                                "value": e.normalized.value,
                                "unit": e.normalized.unit,
                                "source": e.filename,
                                "collected_at": e.collected_at.isoformat() if e.collected_at else None,
                            }
                            for e in day_entries[:3]
                        ],
                        "note": "Conflicting values on the same collection date; highest-confidence parse selected.",
                    }
                )
            if chosen is None or (top.collected_at or datetime.min.replace(tzinfo=timezone.utc)) > (
                chosen.collected_at or datetime.min.replace(tzinfo=timezone.utc)
            ):
                chosen = top

        if chosen is None:
            continue

        snapshot.append(chosen.normalized)
        merge_note = None
        if len(entries_sorted) > 1:
            older = [e for e in entries_sorted if e.source_lab_report_id != chosen.source_lab_report_id]
            if older:
                merge_note = (
                    f"Most recent value selected from {chosen.filename}; "
                    f"{len(older)} prior measurement(s) retained for trend analysis."
                )
        integrated_rows.append(
            {
                "biomarker_name": biomarker_name,
                "value": chosen.normalized.value,
                "unit": chosen.normalized.unit,
                "source_lab_report_id": chosen.source_lab_report_id,
                "collected_at": chosen.collected_at,
                "confidence": chosen.confidence,
                "merge_note": merge_note,
                "is_snapshot": True,
            }
        )
        for entry in entries_sorted:
            if entry.source_lab_report_id == chosen.source_lab_report_id and entry is chosen:
                continue
            integrated_rows.append(
                {
                    "biomarker_name": biomarker_name,
                    "value": entry.normalized.value,
                    "unit": entry.normalized.unit,
                    "source_lab_report_id": entry.source_lab_report_id,
                    "collected_at": entry.collected_at,
                    "confidence": entry.confidence,
                    "merge_note": "Historical measurement retained for trend analysis.",
                    "is_snapshot": False,
                }
            )

    return IntegratedMergeResult(
        snapshot=snapshot,
        integrated_rows=integrated_rows,
        sources=sources,
        conflicts=conflicts,
    )