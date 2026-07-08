"""Evidence Confidence & Explainability Engine — structured, non-LLM transparency layer."""

from app.evidence_confidence.engine import build_explainability_bundle, evaluate_recommendations

__all__ = ["build_explainability_bundle", "evaluate_recommendations"]