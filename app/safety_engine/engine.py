"""Safety Engine v1.0 — evaluate candidate interventions; inform, never decide."""

from __future__ import annotations

from app.models.enums import SafetyRelationshipType, SafetyRiskLevel
from app.safety_engine.legacy_data import (
    _CONTRAINDICATIONS,
    _REGULATED_INTERVENTIONS,
    active_contraindication_keys,
    matched_drug_interactions,
    matched_liver_caution,
)
from app.safety_engine.graph_seed import REGULATED_INTERVENTIONS, edges_for_intervention
from app.safety_engine.patient_context import SafetyPatientContext, build_patient_context
from app.safety_engine.scoring import worst_severity
from app.schemas.pipeline import LLMRecommendation, SafetyReport, ScoredRecommendation
from app.schemas.safety import SafetyEngineInput
from app.schemas.safety_profile import InterventionSafetyProfile, SafetyWarningDetail





def health_profile_conditions(ctx: SafetyPatientContext) -> list[str]:
    """Merge catalog condition keys with legacy CKD/pregnancy phrases for rule matching."""
    phrases = list(ctx.conditions)
    if ctx.pregnancy:
        phrases.append("pregnancy")
    if ctx.kidney_impairment or "kidney_disease" in ctx.conditions:
        phrases.append("severe chronic kidney disease")
    if "autoimmune_disease" in ctx.conditions:
        phrases.append("autoimmune")
    return phrases


def _graph_warnings(
    intervention_name: str,
    ctx: SafetyPatientContext,
) -> list[SafetyWarningDetail]:
    warnings: list[SafetyWarningDetail] = []
    name_lower = intervention_name.lower()

    for edge in edges_for_intervention(intervention_name):
        rel = edge["relationship"]
        target = edge["target"]
        triggered = False
        warning_type = "caution"

        if rel == SafetyRelationshipType.INTERACTS_WITH and target in ctx.medications:
            triggered = True
            warning_type = "interaction"
        elif rel == SafetyRelationshipType.CONTRAINDICATED_IN and target in ctx.conditions:
            triggered = True
            warning_type = "contraindication"
        elif rel in (SafetyRelationshipType.USE_WITH_CAUTION, SafetyRelationshipType.CAUTION_IN):
            if target in ctx.conditions:
                triggered = True
                warning_type = "contraindication" if rel == SafetyRelationshipType.CONTRAINDICATED_IN else "caution"
            elif target == "liver" and ctx.liver_impairment:
                triggered = True
                warning_type = "organ_caution"
            elif target == "kidney" and ctx.kidney_impairment:
                triggered = True
                warning_type = "organ_caution"

        if not triggered:
            continue

        warnings.append(
            SafetyWarningDetail(
                warning_type=warning_type,
                relationship=rel.value,
                severity=edge["severity"],
                mechanism=edge["mechanism"],
                evidence_level=edge.get("evidence_level"),
                citations=list(edge.get("citations") or []),
                source_entity=intervention_name,
                target_entity=target,
                note=edge.get("note"),
            )
        )

    # Legacy pregnancy/CKD exclusions as warnings (not removals)
    profile_conditions = list(health_profile_conditions(ctx))
    contra_keys = active_contraindication_keys({
        "known_conditions": profile_conditions,
        "current_medications": ctx.raw_medications or ctx.medications,
    })
    for key in contra_keys:
        if name_lower in _CONTRAINDICATIONS.get(key, []):
            warnings.append(
                SafetyWarningDetail(
                    warning_type="contraindication",
                    relationship=SafetyRelationshipType.CONTRAINDICATED_IN.value,
                    severity=SafetyRiskLevel.CONTRAINDICATED,
                    mechanism=f"Listed as caution/contraindication for patient context: {key.replace('_', ' ')}.",
                    source_entity=intervention_name,
                    target_entity=key,
                )
            )

    liver_note = matched_liver_caution(intervention_name, {"known_conditions": list(ctx.conditions)})
    if liver_note:
        warnings.append(
            SafetyWarningDetail(
                warning_type="organ_caution",
                relationship=SafetyRelationshipType.CAUTION_IN.value,
                severity=SafetyRiskLevel.MODERATE,
                mechanism=liver_note,
                source_entity=intervention_name,
                target_entity="liver",
            )
        )

    if ctx.pregnancy or ctx.breastfeeding:
        flag = "pregnancy" if ctx.pregnancy else "breastfeeding"
        if name_lower in _CONTRAINDICATIONS.get("pregnancy", []) and not any(
            w.warning_type == "contraindication" for w in warnings
        ):
            warnings.append(
                SafetyWarningDetail(
                    warning_type="pregnancy_lactation",
                    relationship=SafetyRelationshipType.USE_WITH_CAUTION.value,
                    severity=SafetyRiskLevel.MODERATE,
                    mechanism=f"Use caution during {flag}; limited safety data for high-dose extracts.",
                    source_entity=intervention_name,
                    target_entity=flag,
                )
            )

    # Legacy drug interactions not yet in graph
    for entry in matched_drug_interactions(intervention_name, ctx.raw_medications or ctx.medications):
        drug = entry["drug_name"]
        if any(w.target_entity == drug for w in warnings):
            continue
        med_list = ctx.raw_medications or ctx.medications
        if not any(m.lower() in drug.lower() or drug.lower() in m.lower() for m in med_list):
            continue
        warnings.append(
            SafetyWarningDetail(
                warning_type="interaction",
                relationship=SafetyRelationshipType.INTERACTS_WITH.value,
                severity=entry["severity"],
                mechanism=entry.get("mechanism") or "",
                source_entity=intervention_name,
                target_entity=drug,
                note=entry.get("note"),
            )
        )

    return warnings


def _build_safety_profile(
    intervention_name: str,
    warnings: list[SafetyWarningDetail],
    *,
    is_regulated: bool,
    regulation_note: str | None,
) -> InterventionSafetyProfile:
    rating = worst_severity([w.severity for w in warnings] if warnings else [SafetyRiskLevel.LOW])
    contraindications = [
        w.mechanism for w in warnings if w.warning_type == "contraindication"
    ]
    organ_cautions = [
        w.mechanism for w in warnings if w.warning_type == "organ_caution"
    ]
    pregnancy_warnings = [
        w.mechanism for w in warnings if w.warning_type == "pregnancy_lactation"
    ]
    safety_notes: list[str] = []
    if regulation_note:
        safety_notes.append(regulation_note)

    prominent = rating in (SafetyRiskLevel.HIGH, SafetyRiskLevel.CONTRAINDICATED) or bool(contraindications)

    return InterventionSafetyProfile(
        safety_rating=rating,
        warnings=warnings,
        contraindications=contraindications,
        organ_cautions=organ_cautions,
        pregnancy_lactation_warnings=pregnancy_warnings,
        requires_prominent_warning=prominent,
        is_regulated=is_regulated,
        regulation_note=regulation_note,
    )


def evaluate_interventions(
    recommendations: list[LLMRecommendation],
    *,
    health_profile: dict | None = None,
    normalized_labs: list | None = None,
) -> SafetyReport:
    """Safety Engine v1.0 entry point.

    All interventions are retained; high-risk items are flagged and ranked lower downstream.
    """
    profile = health_profile or {}
    ctx = build_patient_context(profile, normalized_labs)

    scored: list[ScoredRecommendation] = []
    high_risk_names: list[str] = []

    for rec in recommendations:
        name_lower = rec.intervention_name.lower()
        regulation_note = REGULATED_INTERVENTIONS.get(name_lower) or _REGULATED_INTERVENTIONS.get(name_lower)
        is_regulated = name_lower in REGULATED_INTERVENTIONS or name_lower in _REGULATED_INTERVENTIONS

        warnings = _graph_warnings(rec.intervention_name, ctx)
        safety_profile = _build_safety_profile(
            rec.intervention_name,
            warnings,
            is_regulated=is_regulated,
            regulation_note=regulation_note,
        )

        interaction_labels: list[str] = []
        seen_interactions: set[str] = set()
        for w in warnings:
            if w.warning_type != "interaction":
                continue
            label = f"{w.target_entity}: {w.mechanism}" + (f" ({w.note})" if w.note else "")
            key = label.lower()
            if key in seen_interactions:
                continue
            seen_interactions.add(key)
            interaction_labels.append(label)
        safety_notes: list[str] = []
        if safety_profile.regulation_note:
            safety_notes.append(safety_profile.regulation_note)
        safety_notes.extend(safety_profile.organ_cautions)
        safety_notes.extend(safety_profile.pregnancy_lactation_warnings)
        safety_notes.extend(safety_profile.contraindications[:2])

        if safety_profile.safety_rating in (SafetyRiskLevel.MODERATE, SafetyRiskLevel.HIGH, SafetyRiskLevel.CONTRAINDICATED):
            high_risk_names.append(rec.intervention_name)

        scored.append(
            ScoredRecommendation(
                **rec.model_dump(),
                safety_risk=safety_profile.safety_rating,
                safety_notes=[n for n in safety_notes if n],
                interactions=interaction_labels or [
                    f"{w.target_entity}: {w.mechanism}" for w in warnings if w.warning_type != "interaction"
                ][:3],
                is_regulated=is_regulated,
                safety_profile=safety_profile,
            )
        )

    requires_review = bool(high_risk_names)
    overall_note = (
        "No major safety concerns detected for the surfaced interventions."
        if not high_risk_names
        else "One or more interventions carry safety warnings — review with a qualified clinician before use."
    )

    return SafetyReport(
        approved_recommendations=scored,
        excluded_recommendations=[],
        requires_clinician_review=requires_review,
        overall_note=overall_note,
    )


def evaluate_from_input(payload: SafetyEngineInput) -> SafetyReport:
    return evaluate_interventions(
        payload.recommendations,
        health_profile=payload.health_profile,
        normalized_labs=payload.normalized_labs,
    )