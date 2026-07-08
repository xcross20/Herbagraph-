"""Deterministic KG fallbacks when pathway/biomarker links are thin."""

from __future__ import annotations

from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS

_PATHWAY_NAMES: dict[str, str] = {}


def _load_pathway_names() -> dict[str, str]:
    global _PATHWAY_NAMES
    if not _PATHWAY_NAMES:
        from app.knowledge_graph.seed_data import PATHWAYS

        _PATHWAY_NAMES = {p["code"]: p["name"] for p in PATHWAYS}
    return _PATHWAY_NAMES


def _all_claims() -> list[dict]:
    return [*EVIDENCE_CLAIMS, *TIER_A_EVIDENCE_CLAIMS]


def catalog_why_surfaced(intervention_name: str, abnormal_biomarkers: set[str]) -> list[str]:
    reasons: list[str] = []
    for claim in _all_claims():
        if claim.get("intervention_name") != intervention_name:
            continue
        biomarker = claim.get("biomarker_name")
        if biomarker and biomarker in abnormal_biomarkers:
            reasons.append(f"{biomarker} abnormal")
        elif biomarker is None and claim.get("pathway_code"):
            reasons.append(f"Catalog link to {claim['pathway_code'].replace('_', ' ').lower()}")
    if not reasons and abnormal_biomarkers:
        reasons.append(f"Abnormal: {', '.join(sorted(abnormal_biomarkers)[:2])}")
    return reasons[:4]


def catalog_pathway_codes(intervention_name: str, abnormal_biomarkers: set[str]) -> list[str]:
    codes: list[str] = []
    for claim in _all_claims():
        if claim.get("intervention_name") != intervention_name:
            continue
        biomarker = claim.get("biomarker_name")
        code = claim.get("pathway_code")
        if code and (biomarker is None or biomarker in abnormal_biomarkers):
            if code not in codes:
                codes.append(code)
    return codes


def pathway_display_name(pathway_code: str) -> str:
    return _load_pathway_names().get(pathway_code, pathway_code.replace("_", "/"))