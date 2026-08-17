"""Open and score investigation branches from a validated plan. LLM cannot close them."""

from __future__ import annotations

from app.discovery.catalog import families_for_concern
from app.discovery.epistemics import EpistemicValidator, coverage_to_evidence_relationship
from app.discovery.mutations import BranchMutation, EvidenceMutation, GapMutation


_DEFAULT_GAPS = {
    "small_fiber_function": ("objective_small_fiber", "Objective small-fiber evaluation", "small_fiber_density"),
    "biliary_colic_pattern": ("fat_trigger_and_episode", "Fat trigger and episode length", None),
    "gastric_dyspeptic_pattern": ("meal_relation", "Meal relation and nausea vs vomiting", None),
    "large_fiber_function": ("emg_protocol", "What the EMG actually tested", "large_fiber_function"),
}


def branches_from_concern(concern: str, extra: str = "") -> list[BranchMutation]:
    blob = f"{concern} {extra}".strip()
    families = families_for_concern(blob)
    opened: list[BranchMutation] = []
    for family in families[:8]:
        opened.append(
            BranchMutation(
                code=family.code,
                label=family.label,
                category=family.branch,
                rationale=family.why_not_a_diagnosis,
                operation="OPEN",
            )
        )
    lowered = blob.lower()
    if "gallbladder" in lowered or "right upper" in lowered or "under my right rib" in lowered:
        if not any(item.code == "biliary_colic_pattern" for item in opened):
            opened.append(
                BranchMutation(
                    code="biliary_colic_pattern",
                    label="Biliary-type episodic pain pattern",
                    category="biliary",
                    rationale="Investigation relevance is not a diagnosis.",
                )
            )
    if "emg" in lowered or "burning" in lowered or "feet" in lowered:
        if not any(item.code == "small_fiber_function" for item in opened):
            opened.append(
                BranchMutation(
                    code="small_fiber_function",
                    label="Small-fiber function",
                    category="peripheral_nerve",
                    rationale="Sensory quality can keep this branch open even after large-fiber testing.",
                )
            )
    return opened


def evidence_for_workup(raw_test: str, branch_code: str) -> EvidenceMutation | None:
    concept = {
        "small_fiber_function": "small_fiber_density",
        "biliary_colic_pattern": "biliary_stones",
        "large_fiber_function": "large_fiber_function",
    }.get(branch_code)
    if not concept:
        return None
    decision = EpistemicValidator().validate_test_inference(raw_test, concept)
    mapped = coverage_to_evidence_relationship(decision.relation)
    if mapped is None:
        return None
    return EvidenceMutation(
        branch_code=branch_code,
        relationship=mapped.value,
        rationale="; ".join(decision.reasons) or None,
        workup_name=raw_test,
    )


def default_gaps_for(branch_code: str) -> list[GapMutation]:
    if branch_code not in _DEFAULT_GAPS:
        return []
    code, label, _concept = _DEFAULT_GAPS[branch_code]
    return [GapMutation(code=code, label=label, branch_code=branch_code)]
