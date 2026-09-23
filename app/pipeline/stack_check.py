"""Deterministic metabolic Stack Check. No LLM. Kernel claims only."""

from __future__ import annotations

from app.models.enums import LabResultStatus
from app.pipeline.biomarker_normalizer import normalize_lab_results
from app.pipeline.metabolic_kernel import (
    METABOLIC_KERNEL,
    is_statin,
    kernel_item,
    resolve_kernel_name,
)
from app.schemas.pipeline import ParsedLabResult

_ABNORMAL = {
    LabResultStatus.LOW,
    LabResultStatus.HIGH,
    LabResultStatus.CRITICAL_LOW,
    LabResultStatus.CRITICAL_HIGH,
}

_FAMILY_MARKERS = {
    "lipid": {"LDL", "HDL", "Triglycerides", "Total Cholesterol", "Non-HDL Cholesterol"},
    "glycemic": {"Glucose", "HbA1c", "Insulin", "HOMA-IR"},
    "hepatic": {"ALT", "AST", "GGT"},
}

HOLD = "hold"
FOOD_FIRST = "food_first"
DISCUSS = "discuss"
MISMATCH = "mismatch"
UNKNOWN = "unknown"


def families_from_labs(normalized) -> set[str]:
    families: set[str] = set()
    abnormal_names = {row.biomarker_name for row in normalized if row.status in _ABNORMAL}
    for family, markers in _FAMILY_MARKERS.items():
        if abnormal_names & markers:
            families.add(family)
    return families


def hepatic_signal(normalized) -> bool:
    return any(
        row.biomarker_name in _FAMILY_MARKERS["hepatic"] and row.status in _ABNORMAL
        for row in normalized
    )


def parse_typed_labs(rows: list[dict]) -> list:
    parsed = []
    for row in rows:
        name = str(row.get("name") or row.get("biomarker_name") or "").strip()
        if not name:
            continue
        try:
            value = float(row.get("value"))
        except (TypeError, ValueError):
            continue
        parsed.append(
            ParsedLabResult(
                raw_test_name=name,
                value=value,
                unit=row.get("unit"),
                reference_range_low=row.get("reference_range_low"),
                reference_range_high=row.get("reference_range_high"),
                parser_pattern="manual",
                parse_confidence=1.0,
            )
        )
    return normalize_lab_results(parsed)


def evaluate_stack(*, labs: list[dict], stack: list[str], medications: list[str] | None = None, conditions: list[str] | None = None, ranking_mode: str = "consumer") -> dict:
    normalized = parse_typed_labs(labs)
    families = families_from_labs(normalized)
    liver = hepatic_signal(normalized)
    meds = [m.strip() for m in (medications or []) if str(m).strip()]
    conds = [c.strip().lower() for c in (conditions or []) if str(c).strip()]
    pregnant = any(token in " ".join(conds) for token in ("pregnan", "trying to conceive"))
    on_statin = any(is_statin(m) for m in meds)
    consumer = ranking_mode != "clinician"
    abnormal = [{"biomarker_name": row.biomarker_name, "value": row.value, "unit": row.unit, "status": row.status.value} for row in normalized if row.status in _ABNORMAL]
    verdicts = []
    for raw in stack:
        name = resolve_kernel_name(raw)
        if name == "Goldenseal":
            verdicts.append({"input": raw, "name": "Goldenseal", "verdict": HOLD if consumer else MISMATCH, "reason": "Goldenseal is not berberine. Lipid and glycemic berberine papers do not transfer."})
            continue
        item = kernel_item(raw)
        if item is None:
            verdicts.append({"input": raw, "name": raw, "verdict": UNKNOWN, "reason": "Not in the metabolic kernel. Ask can investigate a concern; this door will not grade it."})
            continue
        if item.pregnancy_hold and pregnant:
            verdicts.append({"input": raw, "name": item.name, "verdict": HOLD, "reason": f"{item.name} is on hold in pregnancy. Discuss with the clinician managing that pregnancy."})
            continue
        if item.pharmacologic_analogue == "statin" and on_statin:
            verdicts.append({"input": raw, "name": item.name, "verdict": HOLD, "reason": "Red yeast rice is a statin-class analogue (monacolin K). Do not stack on an active statin."})
            continue
        if item.liver_caution and liver:
            verdicts.append({"input": raw, "name": item.name, "verdict": HOLD, "reason": "Hepatic markers are outside range. This item is on hold until a clinician reviews liver safety."})
            continue
        if item.food_first and families.intersection(item.indication_families):
            verdicts.append({"input": raw, "name": item.name, "verdict": FOOD_FIRST, "reason": item.notes or "Food-first option for the measured metabolic pattern."})
            continue
        if families.intersection(item.indication_families):
            verdicts.append({"input": raw, "name": item.name, "verdict": DISCUSS, "reason": f"{item.name} has kernel evidence in {', '.join(sorted(item.indication_families))} and those families are active on this panel. Discuss — not a directive."})
            continue
        verdicts.append({"input": raw, "name": item.name, "verdict": MISMATCH, "reason": "No matching abnormal marker on this panel for that item's indication family."})
    clinician_questions = []
    if on_statin:
        clinician_questions.append("Confirm current statin dose before any monacolin-containing product.")
    if pregnant:
        clinician_questions.append("This stack includes items that are on hold in pregnancy.")
    if liver:
        clinician_questions.append("Repeat or review ALT/AST before cassia cinnamon or red yeast rice.")
    if any(v["verdict"] == DISCUSS and v["name"] == "Berberine" for v in verdicts):
        clinician_questions.append("If discussing berberine, review current glucose-lowering medicines.")
    return {
        "families": sorted(families),
        "abnormal": abnormal,
        "verdicts": verdicts,
        "clinician_questions": clinician_questions,
        "disclaimer": "Not a diagnosis and not a recommendation to start or stop a medicine. Hold means do not add this item until a clinician reviews it.",
        "kernel_version": "metabolic-wedge-v1",
        "follow_up": {"window_weeks": "8-12", "markers": ["LDL", "HDL", "Triglycerides", "HbA1c", "Glucose", "ALT", "AST"], "note": "Same seven markers later. Movement is not proof of cause."},
        "food_first_defaults": [item.name for item in METABOLIC_KERNEL if item.food_first],
    }
