"""Build structured safety patient context from demographics, profile, and labs."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import LabResultStatus
from app.safety_engine.condition_catalog import active_conditions
from app.safety_engine.medication_catalog import matched_patient_medications
from app.schemas.pipeline import NormalizedLabResult


@dataclass
class SafetyPatientContext:
    age_range: str | None = None
    biological_sex: str | None = None
    medications: list[str] = field(default_factory=list)
    raw_medications: list[str] = field(default_factory=list)
    supplements: list[str] = field(default_factory=list)
    conditions: set[str] = field(default_factory=set)
    pregnancy: bool = False
    breastfeeding: bool = False
    liver_impairment: bool = False
    kidney_impairment: bool = False
    egfr: float | None = None
    organ_flags: set[str] = field(default_factory=set)


_LIVER_MARKERS = frozenset({"AST", "ALT", "GGT", "Alkaline Phosphatase"})
_KIDNEY_MARKERS = frozenset({"Creatinine", "eGFR", "BUN"})


def build_patient_context(
    health_profile: dict,
    normalized_labs: list[NormalizedLabResult] | None = None,
) -> SafetyPatientContext:
    conditions_list = list(health_profile.get("known_conditions") or [])
    active = active_conditions(conditions_list)

    raw_meds = list(health_profile.get("current_medications") or [])
    ctx = SafetyPatientContext(
        age_range=health_profile.get("age_range"),
        biological_sex=health_profile.get("biological_sex"),
        medications=matched_patient_medications(raw_meds),
        raw_medications=raw_meds,
        supplements=list(health_profile.get("current_supplements") or []),
        conditions=active,
        pregnancy="pregnancy" in active,
        breastfeeding="breastfeeding" in active,
        liver_impairment="liver_disease" in active,
        kidney_impairment="kidney_disease" in active,
    )

    abnormal = frozenset({"critical_low", "low", "high", "critical_high"})
    for lab in normalized_labs or []:
        if lab.status.value not in abnormal:
            if lab.biomarker_name == "eGFR" and lab.value < 60:
                ctx.kidney_impairment = True
                ctx.egfr = lab.value
                ctx.organ_flags.add("kidney")
            continue

        name = lab.biomarker_name
        if name in _LIVER_MARKERS and lab.status in (LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH):
            ctx.liver_impairment = True
            ctx.organ_flags.add("liver")
        if name == "eGFR" and lab.value < 60:
            ctx.kidney_impairment = True
            ctx.egfr = lab.value
            ctx.organ_flags.add("kidney")
        if name == "Creatinine" and lab.status in (LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH):
            ctx.kidney_impairment = True
            ctx.organ_flags.add("kidney")

    if ctx.liver_impairment:
        ctx.organ_flags.add("liver")
    if ctx.kidney_impairment:
        ctx.organ_flags.add("kidney")

    return ctx