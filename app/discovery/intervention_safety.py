"""Constrained intervention discussion. Commerce cannot change safety or rank."""

from __future__ import annotations

from dataclasses import dataclass

BLOCKING_INTERACTIONS = {
    ("warfarin", "vitamin k"),
    ("warfarin", "dong quai"),
    ("warfarin", "st johns wort"),
    ("warfarin", "st. john's wort"),
}
WARNING_INTERACTIONS = {
    ("warfarin", "ginkgo"),
    ("warfarin", "garlic"),
    ("warfarin", "ginseng"),
}


@dataclass(frozen=True)
class InterventionScreen:
    allowed: bool
    kind: str
    limitations: tuple[str, ...]
    blocks: tuple[str, ...]
    commerce_used: bool = False


def _norm(value: str | None) -> str:
    return " ".join((value or "").lower().replace("'", "").replace("-", " ").split())


def classify_causal_language(*, exposure: str | None, adherence: str | None, user_attribution: bool) -> str:
    if not exposure or _norm(adherence) in {"", "unknown", "missing"}:
        return "insufficient_for_causal_inference"
    if user_attribution:
        return "user_attribution"
    return "temporal_association"


def screen_intervention(
    *,
    intervention: str,
    medications: list[str] | None,
    allergies: list[str] | None = None,
    pregnancy: bool = False,
    gold_label: bool = False,
    claim_kind: str = "education",
) -> InterventionScreen:
    del gold_label  # commerce cannot change eligibility
    name = _norm(intervention)
    meds = [_norm(item) for item in (medications or [])]
    limitations: list[str] = []
    blocks: list[str] = []
    if medications is None:
        limitations.append("missing_medication_data")
    for med in meds:
        pair = (med, name)
        reverse = (name, med)
        if pair in BLOCKING_INTERACTIONS or reverse in BLOCKING_INTERACTIONS:
            blocks.append(f"{med}+{name}")
        elif pair in WARNING_INTERACTIONS or reverse in WARNING_INTERACTIONS:
            limitations.append(f"warning:{med}+{name}")
    allergy_hits = [item for item in (allergies or []) if _norm(item) and _norm(item) in name]
    if allergy_hits:
        blocks.append("allergy")
    if pregnancy:
        limitations.append("pregnancy_requires_clinician")
    if blocks:
        return InterventionScreen(False, "blocked", tuple(limitations), tuple(blocks))
    if claim_kind == "recommendation" and limitations:
        return InterventionScreen(False, "clinician_discussion", tuple(limitations), ())
    if claim_kind not in {"education", "clinician_discussion", "recommendation"}:
        claim_kind = "education"
    return InterventionScreen(True, claim_kind, tuple(limitations), ())
