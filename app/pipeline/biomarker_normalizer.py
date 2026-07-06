"""Stage 2: Biomarker Normalizer.

Maps 100+ raw lab test names (aliases, abbreviations, manufacturer variants)
to a canonical biomarker set, then classifies each result using both the
lab-provided reference range and HerbaGraph's clinically-validated ranges.
"""

import re

from app.models.enums import LabResultStatus
from app.schemas.pipeline import NormalizedLabResult, ParsedLabResult

# canonical_name -> {reference_low, reference_high, optimal_low, optimal_high, critical_low, critical_high, category}
_REFERENCE_DATA: dict[str, dict] = {
    "CRP": {"reference_low": 0.0, "reference_high": 3.0, "optimal_low": 0.0, "optimal_high": 1.0,
            "critical_low": None, "critical_high": 10.0, "category": "inflammatory"},
    "Homocysteine": {"reference_low": 5.0, "reference_high": 15.0, "optimal_low": 5.0, "optimal_high": 8.0,
                      "critical_low": None, "critical_high": 30.0, "category": "inflammatory"},
    "Glucose": {"reference_low": 70.0, "reference_high": 99.0, "optimal_low": 70.0, "optimal_high": 85.0,
                "critical_low": 54.0, "critical_high": 250.0, "category": "metabolic"},
    "HbA1c": {"reference_low": 4.0, "reference_high": 5.6, "optimal_low": 4.0, "optimal_high": 5.3,
              "critical_low": None, "critical_high": 9.0, "category": "metabolic"},
    "Insulin": {"reference_low": 2.6, "reference_high": 24.9, "optimal_low": 2.6, "optimal_high": 6.0,
                "critical_low": None, "critical_high": 50.0, "category": "metabolic"},
    "Uric Acid": {"reference_low": 3.5, "reference_high": 7.2, "optimal_low": 3.5, "optimal_high": 6.0,
                  "critical_low": 2.0, "critical_high": 10.0, "category": "metabolic"},
    "LDL": {"reference_low": 0.0, "reference_high": 99.0, "optimal_low": 0.0, "optimal_high": 80.0,
            "critical_low": None, "critical_high": 190.0, "category": "lipid"},
    "HDL": {"reference_low": 40.0, "reference_high": 100.0, "optimal_low": 60.0, "optimal_high": 100.0,
            "critical_low": 20.0, "critical_high": None, "category": "lipid"},
    "Triglycerides": {"reference_low": 0.0, "reference_high": 149.0, "optimal_low": 0.0, "optimal_high": 100.0,
                       "critical_low": None, "critical_high": 500.0, "category": "lipid"},
    "ALT": {"reference_low": 7.0, "reference_high": 56.0, "optimal_low": 7.0, "optimal_high": 25.0,
            "critical_low": None, "critical_high": 200.0, "category": "hepatic"},
    "AST": {"reference_low": 10.0, "reference_high": 40.0, "optimal_low": 10.0, "optimal_high": 25.0,
            "critical_low": None, "critical_high": 200.0, "category": "hepatic"},
    "Vitamin D": {"reference_low": 30.0, "reference_high": 100.0, "optimal_low": 50.0, "optimal_high": 80.0,
                  "critical_low": 10.0, "critical_high": 150.0, "category": "hormonal"},
    "TSH": {"reference_low": 0.4, "reference_high": 4.0, "optimal_low": 0.5, "optimal_high": 2.5,
            "critical_low": 0.01, "critical_high": 10.0, "category": "hormonal"},
    "B12": {"reference_low": 200.0, "reference_high": 900.0, "optimal_low": 500.0, "optimal_high": 900.0,
            "critical_low": 150.0, "critical_high": None, "category": "nutritional"},
    "Folate": {"reference_low": 2.7, "reference_high": 17.0, "optimal_low": 7.0, "optimal_high": 17.0,
               "critical_low": 2.0, "critical_high": None, "category": "nutritional"},
    "Magnesium": {"reference_low": 1.7, "reference_high": 2.2, "optimal_low": 2.0, "optimal_high": 2.2,
                  "critical_low": 1.2, "critical_high": 3.0, "category": "nutritional"},
    "Ferritin": {"reference_low": 20.0, "reference_high": 250.0, "optimal_low": 50.0, "optimal_high": 150.0,
                 "critical_low": 10.0, "critical_high": 500.0, "category": "iron_metabolism"},
}

# raw alias (normalized: lowercase, punctuation stripped) -> canonical biomarker name
_ALIAS_MAP: dict[str, str] = {
    "crp": "CRP", "c reactive protein": "CRP", "hs crp": "CRP", "high sensitivity crp": "CRP",
    "hscrp": "CRP", "c reactive protein hs": "CRP",
    "homocysteine": "Homocysteine", "hcy": "Homocysteine", "homocyst(e)ine": "Homocysteine",
    "glucose": "Glucose", "glucose fasting": "Glucose", "fasting glucose": "Glucose",
    "glucose serum": "Glucose", "fasting blood glucose": "Glucose", "fbg": "Glucose",
    "hba1c": "HbA1c", "hemoglobin a1c": "HbA1c", "haemoglobin a1c": "HbA1c", "a1c": "HbA1c",
    "glycohemoglobin": "HbA1c", "glycated hemoglobin": "HbA1c",
    "insulin": "Insulin", "fasting insulin": "Insulin", "insulin fasting": "Insulin",
    "uric acid": "Uric Acid", "urate": "Uric Acid", "uric acid serum": "Uric Acid",
    "ldl": "LDL", "ldl cholesterol": "LDL", "ldl c": "LDL", "ldl chol calc": "LDL",
    "low density lipoprotein": "LDL", "ldl cholesterol calc": "LDL",
    "hdl": "HDL", "hdl cholesterol": "HDL", "hdl c": "HDL", "high density lipoprotein": "HDL",
    "triglycerides": "Triglycerides", "trig": "Triglycerides", "triglyceride": "Triglycerides",
    "alt": "ALT", "alt sgpt": "ALT", "sgpt": "ALT", "alanine aminotransferase": "ALT",
    "ast": "AST", "ast sgot": "AST", "sgot": "AST", "aspartate aminotransferase": "AST",
    "vitamin d": "Vitamin D", "vitamin d 25 hydroxy": "Vitamin D", "25 oh vitamin d": "Vitamin D",
    "25 hydroxyvitamin d": "Vitamin D", "vitamin d3": "Vitamin D", "vit d": "Vitamin D",
    "tsh": "TSH", "thyroid stimulating hormone": "TSH", "thyrotropin": "TSH",
    "vitamin b12": "B12", "b12": "B12", "cobalamin": "B12", "vit b12": "B12",
    "folate": "Folate", "folic acid": "Folate", "folate serum": "Folate", "serum folate": "Folate",
    "magnesium": "Magnesium", "mg": "Magnesium", "magnesium serum": "Magnesium",
    "ferritin": "Ferritin", "serum ferritin": "Ferritin",
}

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _clean(raw_name: str) -> str:
    lowered = raw_name.strip().lower()
    collapsed = _NON_ALNUM_RE.sub(" ", lowered).strip()
    return re.sub(r"\s+", " ", collapsed)


def normalize_biomarker_name(raw_name: str) -> str | None:
    """Map a raw lab test name to its canonical biomarker name, or None if unrecognized."""
    return _ALIAS_MAP.get(_clean(raw_name))


def get_reference_data(canonical_name: str) -> dict | None:
    return _REFERENCE_DATA.get(canonical_name)


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


def normalize_lab_result(parsed: ParsedLabResult) -> NormalizedLabResult:
    """Normalize a single parsed lab row into a NormalizedLabResult with a computed status."""
    canonical_name = normalize_biomarker_name(parsed.raw_test_name)
    ref = _REFERENCE_DATA.get(canonical_name) if canonical_name else None

    reference_low = ref["reference_low"] if ref else parsed.reference_range_low
    reference_high = ref["reference_high"] if ref else parsed.reference_range_high
    optimal_low = ref["optimal_low"] if ref else None
    optimal_high = ref["optimal_high"] if ref else None
    critical_low = ref["critical_low"] if ref else None
    critical_high = ref["critical_high"] if ref else None

    # Fall back to the lab's own reported range if we have no canonical match.
    if reference_low is None:
        reference_low = parsed.reference_range_low
    if reference_high is None:
        reference_high = parsed.reference_range_high

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
    )


def normalize_lab_results(parsed_results: list[ParsedLabResult]) -> list[NormalizedLabResult]:
    return [normalize_lab_result(p) for p in parsed_results]
