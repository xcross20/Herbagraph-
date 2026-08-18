"""Issue 64 Slice A/C: conservative supportive actions. Not a treatment engine."""

from __future__ import annotations

from app.discovery.usefulness import ControlState


def supportive_actions_enabled() -> bool:
    from app.config import get_settings

    return bool(getattr(get_settings(), "supportive_actions_v1", False))


def supplement_discussion_enabled() -> bool:
    from app.config import get_settings

    return bool(getattr(get_settings(), "supplement_discussion_v1", False))


def build_action_plan(
    *,
    control: ControlState | dict | None,
    facts: dict[str, str],
    safety_state: str,
    family_ids: list[str],
    snapshot_id: str,
) -> dict:
    del control
    safety_first = safety_state in {"S3", "S4"}
    options = []
    avoid = []
    if not safety_first:
        if facts.get("fatty_food") == "triggers" or facts.get("meal_relation") or facts.get("location") == "ruq":
            options.append(
                {
                    "id": "sa-avoid-reported-fat-trigger",
                    "category": "diet_pattern",
                    "label": "Temporarily avoid a repeatedly reported fatty-meal trigger",
                    "intended_outcome": "trigger_reduction",
                    "evidence_strength": "plausible_option",
                    "data_completeness": "symptom_reported_only",
                    "does_not": "This does not treat, prove, or exclude a biliary or gastric cause.",
                    "stop_if": "Worsening pain, fever, vomiting, or yellowing needs in-person evaluation.",
                    "authorization": "none",
                    "commerce_neutral": True,
                }
            )
            options.append(
                {
                    "id": "sa-episode-log",
                    "category": "monitoring",
                    "label": "Keep a short meal-and-episode log until testing",
                    "intended_outcome": "observation_quality",
                    "evidence_strength": "well-supported_option",
                    "data_completeness": "symptom_reported_only",
                    "does_not": "Logging does not diagnose or replace indicated evaluation.",
                    "stop_if": "New red-flag symptoms.",
                    "authorization": "none",
                    "commerce_neutral": True,
                }
            )
        avoid.append(
            {
                "id": "sa-avoid-extreme-fast",
                "category": "diet_pattern",
                "label": "Do not use prolonged fasting or rapid restriction as default relief",
                "reason": "Extreme fasting is not a first-line comfort measure and can add risk.",
            }
        )
        avoid.append(
            {
                "id": "sa-avoid-bile-stimulant",
                "category": "supplement_discussion",
                "label": "No bile-flow herb, bile acid, or supplement stack from symptoms alone",
                "reason": "Obstruction and form-specific safety are unresolved. Supplement discussion stays gated.",
            }
        )
    return {
        "version": "action-plan-v1",
        "snapshot_id": snapshot_id,
        "response_mode": "SUPPORTIVE_ACTIONS",
        "safety_state": safety_state,
        "family_ids": list(family_ids),
        "safety_first": safety_first,
        "options": [] if safety_first else options,
        "avoid": avoid,
        "next_evaluation": "Highest-value next evaluation remains the canonical map candidate, not a HIDA-first shortcut.",
        "supplements_eligible": False,
        "disclaimer": "Supportive options are not a diagnosis, prescription, or treatment plan.",
    }


def render_action_plan(plan: dict) -> str:
    if plan.get("safety_first"):
        return (
            "Safety comes first. I will not give ordinary relief suggestions until urgent in-person evaluation is considered. "
            "This is not a diagnosis."
        )
    options = plan.get("options") or []
    avoids = plan.get("avoid") or []
    opt_line = "; ".join(item.get("label") or "" for item in options[:3])
    avoid_line = "; ".join(item.get("label") or "" for item in avoids[:3])
    return (
        "You asked for something useful now, so I will not ask another intake question first. "
        "Meal-associated right-upper discomfort can support a biliary-type investigation family; it does not establish gallbladder disease. "
        "Unverified “normal bloodwork” does not exclude biliary, gastric, or other causes. "
        f"Low-risk options now: {opt_line or 'episode tracking only'}. "
        f"Avoid for now: {avoid_line}. "
        "I will not recommend a HIDA scan as the first or only next step, and I will not suggest bile-flow supplements. "
        f"{plan.get('next_evaluation')} {plan.get('disclaimer')}"
    )
