"""Stage 6: Safety Layer — thin adapter to Safety Engine v1.0.

The Safety Engine is an independent module (`app.safety_engine`) that annotates and ranks
interventions for clinician review. It does NOT remove recommendations from the report.
"""

from __future__ import annotations

from app.safety_engine.engine import evaluate_interventions
from app.schemas.pipeline import LLMRecommendation, SafetyReport

# Re-export legacy helpers for tests and gradual migration.
from app.safety_engine.legacy_data import (  # noqa: F401
    _CONTRAINDICATIONS,
    _DRUG_HERB_INTERACTIONS,
    _REGULATED_INTERVENTIONS,
    active_contraindication_keys as _active_contraindication_keys,
    matched_drug_interactions as _matched_drug_interactions,
    matched_liver_caution as _matched_liver_caution,
)


def check_safety(
    recommendations: list[LLMRecommendation],
    health_profile: dict,
    normalized_labs: list | None = None,
) -> SafetyReport:
    """Stage 6 entry point — delegates to Safety Engine v1.0."""
    return evaluate_interventions(
        recommendations,
        health_profile=health_profile,
        normalized_labs=normalized_labs,
    )