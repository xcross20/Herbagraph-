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

# Differential absolute counts: catalog is cells/µL; portals often report x10E3/µL (K/µL).
# Do NOT include WBC / Platelet Count — catalog and portals both use K/µL scale.
_ABS_COUNT_NAMES = frozenset(
    {
        "absolute lymphocytes",
        "absolute neutrophils",
        "absolute monocytes",
        "absolute basophils",
        "absolute eosinophils",
        "absolute immature granulocytes",
    }
)
_X10E3_UNIT = re.compile(
    r"(?:x\s*10\s*e?\s*3|10\^?\s*e?\s*3|x10e3|10e3|k)\s*/?\s*(?:u|µ|μ)?l|"
    r"thou(?:sand)?s?\s*/?\s*(?:u|µ|μ)?l|k/u?l",
    re.IGNORECASE,
)
_CELLS_UNIT = re.compile(r"cells?\s*/?\s*(?:u|µ|μ)?l", re.IGNORECASE)
_K_CATALOG_UNIT = re.compile(
    r"(?:^k\s*/\s*(?:u|µ|μ)?l$|x\s*10|10e3|10\^3|thou)",
    re.IGNORECASE,
)

# Adult sex-specific CBC ranges when lab PDF range is missing (g/dL, %).
_SEX_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "hemoglobin": {"female": (12.0, 15.5), "male": (13.2, 17.1)},
    "hematocrit": {"female": (36.0, 46.0), "male": (38.5, 50.0)},
}


def _normalize_sex(sex: str | None) -> str | None:
    if not sex:
        return None
    s = str(sex).strip().lower()
    if s in {"f", "female", "woman", "w"}:
        return "female"
    if s in {"m", "male", "man"}:
        return "male"
    return None


def _is_absolute_count_analyte(canonical_name: str | None) -> bool:
    if not canonical_name:
        return False
    key = canonical_name.strip().lower()
    return key in _ABS_COUNT_NAMES or key.startswith("absolute ")


def _align_absolute_count_scale(
    *,
    canonical_name: str | None,
    value: float,
    unit: str | None,
    lab_low: float | None,
    lab_high: float | None,
    ref: dict | None,
) -> tuple[float, str | None, float | None, float | None]:
    """Convert K/µL (x10E3/uL) absolute counts to cells/µL when catalog uses cells scale.

    Returns (value, unit, lab_low, lab_high) on a consistent scale for classification.
    Lab ranges are scaled with the value so portal bounds stay valid after conversion.
    """
    if not _is_absolute_count_analyte(canonical_name):
        return value, unit, lab_low, lab_high

    cat_high = (ref or {}).get("reference_high")
    cat_unit = (ref or {}).get("default_unit")
    unit_s = (unit or "").strip()

    # Never convert when catalog is already on K/µL (or unit says so).
    if cat_unit and _K_CATALOG_UNIT.search(str(cat_unit).strip()):
        return value, unit, lab_low, lab_high

    catalog_is_cells = bool(
        (cat_unit and _CELLS_UNIT.search(str(cat_unit)))
        or (cat_high is not None and cat_high >= 200)
    )
    if not catalog_is_cells:
        return value, unit, lab_low, lab_high

    looks_k = bool(unit_s and _X10E3_UNIT.search(unit_s)) or (
        # Magnitude heuristic when unit missing/ambiguous: portal K/µL diffs are << 100
        value < 100
        and (lab_high is None or lab_high < 100)
        and (cat_high is not None and cat_high >= 200)
    )

    if looks_k and value < 100:
        scale = 1000.0
        value = value * scale
        lab_low = lab_low * scale if lab_low is not None else None
        lab_high = lab_high * scale if lab_high is not None else None
        return value, (cat_unit or "cells/uL"), lab_low, lab_high

    return value, unit, lab_low, lab_high


def _resolve_reference_bounds(
    *,
    ref: dict | None,
    lab_low: float | None,
    lab_high: float | None,
    canonical_name: str | None,
    sex: str | None,
) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    """Prefer lab-provided ranges when present; apply sex-specific CBC defaults when needed."""
    sex_key = _normalize_sex(sex)
    cat_low = ref["reference_low"] if ref else None
    cat_high = ref["reference_high"] if ref else None
    optimal_low = ref["optimal_low"] if ref else None
    optimal_high = ref["optimal_high"] if ref else None
    critical_low = ref["critical_low"] if ref else None
    critical_high = ref["critical_high"] if ref else None

    # Lab PDF ranges are patient/method-specific — prefer when both bounds exist
    # and are on a coherent scale with each other.
    if lab_low is not None and lab_high is not None and lab_high > lab_low:
        return lab_low, lab_high, lab_low, lab_high, critical_low, critical_high

    # Sex-specific catalog overrides for Hgb/Hct when lab omitted range
    if canonical_name and sex_key:
        key = canonical_name.strip().lower()
        if key in _SEX_RANGES:
            lo, hi = _SEX_RANGES[key][sex_key]
            return lo, hi, lo, hi, critical_low, critical_high

    return cat_low, cat_high, optimal_low, optimal_high, critical_low, critical_high


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
    *,
    sex: str | None = None,
) -> NormalizedLabResult:
    """Normalize a single parsed lab row into a NormalizedLabResult with a computed status."""
    canonical_name = normalize_biomarker_name(parsed.raw_test_name, custom_biomarkers)
    ref = reference_data_for_name(canonical_name, custom_biomarkers) if canonical_name else None

    value = parsed.value
    unit = parsed.unit
    lab_low, lab_high = parsed.reference_range_low, parsed.reference_range_high
    value, unit, lab_low, lab_high = _align_absolute_count_scale(
        canonical_name=canonical_name,
        value=value,
        unit=unit,
        lab_low=lab_low,
        lab_high=lab_high,
        ref=ref,
    )

    (
        reference_low,
        reference_high,
        optimal_low,
        optimal_high,
        critical_low,
        critical_high,
    ) = _resolve_reference_bounds(
        ref=ref,
        lab_low=lab_low,
        lab_high=lab_high,
        canonical_name=canonical_name,
        sex=sex,
    )

    if reference_low is None:
        reference_low = lab_low
    if reference_high is None:
        reference_high = lab_high

    qualitative_label = parsed.qualitative_result or (
        unit if _is_qualitative(ref, parsed) and unit and not str(unit).isdigit() else None
    )

    if _is_qualitative(ref, parsed):
        status = _classify_qualitative(parsed)
    else:
        status = classify_lab_value(
            value, reference_low, reference_high, optimal_low, optimal_high, critical_low, critical_high
        )

    return NormalizedLabResult(
        biomarker_name=canonical_name or parsed.raw_test_name,
        raw_test_name=parsed.raw_test_name,
        value=value,
        unit=unit,
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
    *,
    sex: str | None = None,
) -> list[NormalizedLabResult]:
    return [
        normalize_lab_result(p, custom_biomarkers=custom_biomarkers, sex=sex)
        for p in parsed_results
    ]


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
    *,
    sex: str | None = None,
) -> NormalizedLabResult:
    """Convert a persisted LabResult ORM row back into a NormalizedLabResult."""
    raw_test_name = lab_result.raw_test_name or lab_result.biomarker_name
    # Re-run full normalize path so unit scaling + lab-range preference apply on read.
    from app.schemas.pipeline import ParsedLabResult as _Parsed

    parsed = _Parsed(
        raw_test_name=raw_test_name,
        value=float(lab_result.value),
        unit=lab_result.unit,
        reference_range_low=lab_result.reference_range_low,
        reference_range_high=lab_result.reference_range_high,
    )
    # Force canonical name if stored name is already resolved
    result = normalize_lab_result(parsed, custom_biomarkers=custom_biomarkers, sex=sex)
    resolved = _resolve_persisted_canonical_name(
        lab_result.biomarker_name,
        raw_test_name,
        custom_biomarkers,
    )
    if resolved and result.biomarker_name != resolved:
        # Re-normalize with the stored raw name already mapped
        parsed2 = _Parsed(
            raw_test_name=resolved,
            value=float(lab_result.value),
            unit=lab_result.unit,
            reference_range_low=lab_result.reference_range_low,
            reference_range_high=lab_result.reference_range_high,
        )
        result = normalize_lab_result(parsed2, custom_biomarkers=custom_biomarkers, sex=sex)
    return result


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
    *,
    sex: str | None = None,
) -> list[NormalizedLabResult]:
    return [
        normalized_result_from_lab_result(r, custom_biomarkers=custom_biomarkers, sex=sex)
        for r in lab_report.lab_results
    ]


def refresh_persisted_lab_results(
    lab_results,
    custom_biomarkers: list[dict] | None = None,
    *,
    sex: str | None = None,
) -> int:
    """Re-resolve stored lab rows (aliases, unit scale, lab-range preference, sex ranges)."""
    updated = 0
    for row in lab_results:
        normalized = normalized_result_from_lab_result(
            row, custom_biomarkers=custom_biomarkers, sex=sex
        )
        changed = False
        if normalized.biomarker_name != row.biomarker_name:
            row.biomarker_name = normalized.biomarker_name
            changed = True
        if normalized.status != row.status:
            row.status = normalized.status
            changed = True
        if normalized.value != row.value:
            row.value = normalized.value
            changed = True
        if normalized.unit != row.unit:
            row.unit = normalized.unit
            changed = True
        if normalized.reference_range_low != row.reference_range_low:
            row.reference_range_low = normalized.reference_range_low
            changed = True
        if normalized.reference_range_high != row.reference_range_high:
            row.reference_range_high = normalized.reference_range_high
            changed = True
        if changed:
            updated += 1
    return updated
