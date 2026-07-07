"""Stage 2: Biomarker Normalizer.

Maps 500+ raw lab test names (aliases, abbreviations, manufacturer variants)
to a canonical biomarker set of 200+ commonly ordered clinical tests, then
classifies each result using both the lab-provided reference range and
HerbaGraph's clinically-validated ranges.

Biomarkers outside the catalog still get a row and a NORMAL/LOW/HIGH
classification against their own lab-provided range; they just aren't fed
into pathway mapping unless a pathway rule exists for them.
"""

import re

from app.knowledge_graph.biomarker_catalog import REFERENCE_DATA
from app.models.enums import LabResultStatus
from app.pipeline.user_biomarker_profile import (
    is_catalog_biomarker,
    reference_data_for_name,
    resolve_canonical_name,
)
from app.schemas.pipeline import NormalizedLabResult, ParsedLabResult

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _clean(raw_name: str) -> str:
    lowered = raw_name.strip().lower()
    collapsed = _NON_ALNUM_RE.sub(" ", lowered).strip()
    return re.sub(r"\s+", " ", collapsed)


def normalize_biomarker_name(
    raw_name: str,
    custom_biomarkers: list[dict] | None = None,
) -> str | None:
    """Map a raw lab test name to its canonical biomarker name, or None if unrecognized."""
    return resolve_canonical_name(raw_name, custom_biomarkers)


def get_reference_data(canonical_name: str) -> dict | None:
    return REFERENCE_DATA.get(canonical_name)


def classify_lab_value(
    value: float,
    reference_low: float | None,
    reference_high: float | None,
    optimal_low: float | None = None,
    optimal_high: float | None = None,
    critical_low: float | None = None,
    critical_high: float | None = None,
) -> LabResultStatus:
    """Classify a numeric lab value against reference/optimal/critical ranges."""
    if critical_low is not None and value <= critical_low:
        return LabResultStatus.CRITICAL_LOW
    if critical_high is not None and value >= critical_high:
        return LabResultStatus.CRITICAL_HIGH
    if reference_low is not None and value < reference_low:
        return LabResultStatus.LOW
    if reference_high is not None and value > reference_high:
        return LabResultStatus.HIGH
    if optimal_low is not None and optimal_high is not None and optimal_low <= value <= optimal_high:
        return LabResultStatus.OPTIMAL
    return LabResultStatus.NORMAL


_NON_NUMERIC_KINDS = frozenset({"qualitative", "culture", "genotype"})


def _is_non_numeric(ref: dict | None, parsed: ParsedLabResult) -> bool:
    if parsed.qualitative_result is not None:
        return True
    return ref is not None and ref.get("result_kind") in _NON_NUMERIC_KINDS


def _is_qualitative(ref: dict | None, parsed: ParsedLabResult) -> bool:
    return _is_non_numeric(ref, parsed)


def _classify_qualitative(parsed: ParsedLabResult) -> LabResultStatus:
    if parsed.value >= 1.0:
        return LabResultStatus.HIGH
    return LabResultStatus.OPTIMAL


def normalize_lab_result(
    parsed: ParsedLabResult,
    custom_biomarkers: list[dict] | None = None,
) -> NormalizedLabResult:
    """Normalize a single parsed lab row into a NormalizedLabResult with a computed status."""
    canonical_name = normalize_biomarker_name(parsed.raw_test_name, custom_biomarkers)
    ref = reference_data_for_name(canonical_name, custom_biomarkers) if canonical_name else None

    reference_low = ref["reference_low"] if ref else parsed.reference_range_low
    reference_high = ref["reference_high"] if ref else parsed.reference_range_high
    optimal_low = ref["optimal_low"] if ref else None
    optimal_high = ref["optimal_high"] if ref else None
    critical_low = ref["critical_low"] if ref else None
    critical_high = ref["critical_high"] if ref else None

    if reference_low is None:
        reference_low = parsed.reference_range_low
    if reference_high is None:
        reference_high = parsed.reference_range_high

    qualitative_label = parsed.qualitative_result or (
        parsed.unit if _is_qualitative(ref, parsed) and parsed.unit and not parsed.unit.isdigit() else None
    )

    if _is_qualitative(ref, parsed):
        status = _classify_qualitative(parsed)
    else:
        status = classify_lab_value(
            parsed.value, reference_low, reference_high, optimal_low, optimal_high, critical_low, critical_high
        )

    return NormalizedLabResult(
        biomarker_name=canonical_name or parsed.raw_test_name,
        raw_test_name=parsed.raw_test_name,
        value=parsed.value,
        unit=parsed.unit,
        reference_range_low=reference_low,
        reference_range_high=reference_high,
        status=status,
        category=ref["category"] if ref else None,
        qualitative_label=qualitative_label,
        expected_label=parsed.expected_result,
    )


def normalize_lab_results(
    parsed_results: list[ParsedLabResult],
    custom_biomarkers: list[dict] | None = None,
) -> list[NormalizedLabResult]:
    return [normalize_lab_result(p, custom_biomarkers=custom_biomarkers) for p in parsed_results]


def _resolve_persisted_canonical_name(
    biomarker_name: str,
    raw_test_name: str | None,
    custom_biomarkers: list[dict] | None = None,
) -> str:
    """Re-resolve stored lab rows to catalog canonical names (aliases may have been added after upload)."""
    for candidate in (raw_test_name, biomarker_name):
        if not candidate:
            continue
        resolved = resolve_canonical_name(candidate, custom_biomarkers)
        if resolved:
            return resolved
    return biomarker_name


def normalized_result_from_lab_result(
    lab_result,
    custom_biomarkers: list[dict] | None = None,
) -> NormalizedLabResult:
    """Convert a persisted LabResult ORM row back into a NormalizedLabResult."""
    raw_test_name = lab_result.raw_test_name or lab_result.biomarker_name
    canonical_name = _resolve_persisted_canonical_name(
        lab_result.biomarker_name,
        raw_test_name,
        custom_biomarkers,
    )
    ref = reference_data_for_name(canonical_name, custom_biomarkers)

    reference_low = ref["reference_low"] if ref else lab_result.reference_range_low
    reference_high = ref["reference_high"] if ref else lab_result.reference_range_high
    optimal_low = ref["optimal_low"] if ref else None
    optimal_high = ref["optimal_high"] if ref else None
    critical_low = ref["critical_low"] if ref else None
    critical_high = ref["critical_high"] if ref else None

    if reference_low is None:
        reference_low = lab_result.reference_range_low
    if reference_high is None:
        reference_high = lab_result.reference_range_high

    result_kind = (ref or {}).get("result_kind", "numeric")
    qualitative_label = (
        lab_result.unit
        if result_kind == "qualitative" and lab_result.unit and not str(lab_result.unit).isdigit()
        else None
    )

    if result_kind in _NON_NUMERIC_KINDS or qualitative_label:
        status = LabResultStatus.HIGH if lab_result.value >= 1.0 else LabResultStatus.OPTIMAL
    elif is_catalog_biomarker(canonical_name) and ref:
        status = classify_lab_value(
            lab_result.value,
            reference_low,
            reference_high,
            optimal_low,
            optimal_high,
            critical_low,
            critical_high,
        )
    else:
        status = lab_result.status

    return NormalizedLabResult(
        biomarker_name=canonical_name,
        raw_test_name=raw_test_name,
        value=lab_result.value,
        unit=lab_result.unit,
        reference_range_low=reference_low,
        reference_range_high=reference_high,
        status=status,
        category=ref["category"] if ref else None,
        qualitative_label=qualitative_label,
    )


def canonical_name_for_persist(
    result: NormalizedLabResult,
    custom_biomarkers: list[dict] | None = None,
) -> str:
    """Canonical biomarker_name to store on LabResult at upload time."""
    return _resolve_persisted_canonical_name(
        result.biomarker_name,
        result.raw_test_name,
        custom_biomarkers,
    )


def normalized_results_from_lab_report(
    lab_report,
    custom_biomarkers: list[dict] | None = None,
) -> list[NormalizedLabResult]:
    return [
        normalized_result_from_lab_result(r, custom_biomarkers=custom_biomarkers)
        for r in lab_report.lab_results
    ]