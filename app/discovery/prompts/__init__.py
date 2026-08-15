"""Compose Discovery Guide system prompts from versioned policy files."""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent

_PASS_A_FILES = (
    "core_identity.md",
    "epistemic_policy.md",
    "safety_policy.md",
    "consumer_claims_policy.md",
    "literature_policy.md",
    "memory_policy.md",
    "investigation_policy.md",
    "coverage_policy.md",
    "retraction_policy.md",
    "intervention_policy.md",
)

_PASS_B_FILES = (
    "core_identity.md",
    "conversation_style.md",
    "epistemic_policy.md",
    "safety_policy.md",
    "consumer_claims_policy.md",
)


def _read(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8").strip()


def compose_prompt(names: tuple[str, ...]) -> str:
    return "\n\n".join(_read(name) for name in names)


def pass_a_system_prompt() -> str:
    return (
        compose_prompt(_PASS_A_FILES)
        + "\n\nReturn JSON only with this shape:\n"
        '{"user_intents":[],"reported_facts":[{"concept":"","type":"symptom","value":""}],'
        '"patient_interpretations":[],"timeline_updates":[],'
        '"prior_workup":[{"test":"","result":"","verification":"patient_reported"}],'
        '"contradictions":[],"safety_flags":[],"uncertainty_updates":[],'
        '"literature_queries":[],"action_candidates":[{"type":"ASK_QUESTION","prompt":"","reason":"","options":[]}],'
        '"recommended_next_action":{"type":"ASK_QUESTION","prompt":"","reason":"","options":[]},'
        '"problem_representation":"","missing_dimensions":[],"reasoning_summary":"","wants_evidence":false}\n'
        "action type must be one of ASK_QUESTION, ASK_SMALL_GROUP, REFLECT, CLARIFY, "
        "SEARCH_LITERATURE, REQUEST_RECORD, SHOW_INVESTIGATION_MAP, ESCALATE_SAFETY.\n"
        "Do not diagnose. Facts are reported only. Interpretations stay in patient_interpretations "
        "as strings. Parse the entire story — keep odd triggers, failed treatments, and incomplete "
        "threads as separate items. Do not collapse a complex case into one symptom."
    )


def pass_b_system_prompt() -> str:
    return (
        compose_prompt(_PASS_B_FILES)
        + "\n\nYou verbalize a predetermined Discovery action. Do not change the action. "
        "Write as a personal health guide for this one person. Integrate their story with the person_context you are given. "
        "Do not diagnose. Do not invent labs or citations. "
        "JSON {\"message\":\"\"}."
    )
