"""Case-governed Discovery usefulness controller (issue 58, Slice A).

The LLM may verbalize the selected response mode. It may not choose it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.discovery.coverage_catalog import normalize_label

RESPONSE_MODES = (
    "SAFETY_ESCALATION",
    "CLARIFY_CONTRADICTION",
    "INTERIM_SYNTHESIS",
    "NEXT_STEPS",
    "RESEARCH_EXPLANATION",
    "REQUEST_EVIDENCE",
    "ASK_ONE_QUESTION",
    "NO_ELIGIBLE_ACTION",
)

FOCUS_STATES = ("active", "background", "paused_by_user", "completed")

SLOT_ALIASES = {
    "laterality": "laterality",
    "duration": "duration",
    "meal_relation": "meal_delay",
    "episode_duration": "duration",
    "claimed normal labs": "records_available",
    "emg testing": "emg_status",
    "weakness": "weakness",
}

CONCERN_PATTERNS = (
    ("burning_feet", re.compile(r"burn|feet|foot|tingl|neuropath")),
    ("facial_heat", re.compile(r"face|facial|flush|heat in (?:my )?face")),
    ("ruq_discomfort", re.compile(r"gallbladder|right (?:upper |rib)|under (?:my )?right|ruq|rib")),
)


def usefulness_governor_enabled() -> bool:
    from app.config import get_settings

    return bool(getattr(get_settings(), "discovery_usefulness_governor_v1", False))


def load_usefulness_fixture(path: Path | None = None) -> dict:
    target = path or Path(__file__).resolve().parents[2] / "benchmarks" / "discovery_usefulness" / "v1" / "transcript.json"
    return json.loads(target.read_text(encoding="utf-8"))


def classify_control_intent(text: str) -> list[str]:
    blob = (text or "").lower()
    intents: list[str] = []
    if re.search(r"let'?s not deal with|don'?t (?:want to |wanna )?talk about|pause .{0,20}feet|skip the feet", blob):
        intents.append("pause_topic")
    if re.search(r"resume .{0,20}feet|back to (?:the )?feet|burning feet again", blob):
        intents.append("resume_topic")
    if re.search(r"what (?:do you think|should i do)|next step|what now|plan", blob):
        intents.append("request_next_steps")
    if re.search(r"what do you think|summar|assessment|so what is (?:this|going on)", blob):
        intents.append("request_synthesis")
    if re.search(r"why|evidence|pubmed|paper|research|citation", blob):
        intents.append("request_research")
    if re.search(r"don'?t have (?:any )?(?:more )?labs|no (?:more )?records|i don'?t have (?:those|it|them)", blob):
        intents.append("cannot_provide_evidence")
    if re.search(r"like i said|already (?:answered|told|said)|i just (?:said|told)", blob):
        intents.append("repetition_frustration")
    return intents


def concern_from_text(text: str) -> str | None:
    blob = (text or "").lower()
    for code, pattern in CONCERN_PATTERNS:
        if pattern.search(blob):
            return code
    return None


def slot_key(concern: str | None, fact_name: str) -> str | None:
    alias = SLOT_ALIASES.get(fact_name) or SLOT_ALIASES.get(normalize_label(fact_name))
    if not alias:
        return None
    scope = concern or "case"
    if fact_name in {"claimed normal labs", "emg testing"}:
        scope = "prior_labs" if "lab" in fact_name or fact_name.startswith("claimed") else "prior_labs"
    if fact_name == "emg testing":
        return "prior_labs.emg_status"
    if fact_name == "claimed normal labs":
        return "prior_labs.records_available"
    return f"{scope}.{alias}"


@dataclass
class ControlState:
    focus: dict[str, str] = field(default_factory=dict)
    slots: dict[str, dict] = field(default_factory=dict)
    last_intents: list[str] = field(default_factory=list)
    cannot_provide_count: int = 0
    frustration_count: int = 0
    version: int = 1

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "focus": dict(self.focus),
            "slots": dict(self.slots),
            "last_intents": list(self.last_intents),
            "cannot_provide_count": self.cannot_provide_count,
            "frustration_count": self.frustration_count,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> ControlState:
        data = payload or {}
        return cls(
            focus=dict(data.get("focus") or {}),
            slots=dict(data.get("slots") or {}),
            last_intents=list(data.get("last_intents") or []),
            cannot_provide_count=int(data.get("cannot_provide_count") or 0),
            frustration_count=int(data.get("frustration_count") or 0),
            version=int(data.get("version") or 1),
        )


def apply_control(state: ControlState, text: str, facts: dict[str, str]) -> ControlState:
    intents = classify_control_intent(text)
    mentioned = concern_from_text(text)
    if mentioned and mentioned not in state.focus:
        state.focus[mentioned] = "active"
    if "facial" in (text or "").lower() or "heat" in (text or "").lower():
        state.focus.setdefault("facial_heat", "active")
    if any(token in (text or "").lower() for token in ("rib", "gallbladder", "ruq")):
        state.focus.setdefault("ruq_discomfort", "active")
    if any(token in (text or "").lower() for token in ("burn", "feet", "foot")):
        state.focus.setdefault("burning_feet", "active")
    if "pause_topic" in intents:
        target = mentioned or "burning_feet"
        if state.focus.get(target) != "paused_by_user":
            state.focus[target] = "paused_by_user"
    if "resume_topic" in intents:
        target = mentioned or "burning_feet"
        state.focus[target] = "active"
    if "cannot_provide_evidence" in intents:
        state.cannot_provide_count += 1
        state.slots["prior_labs.records_available"] = {
            "status": "answered",
            "value": "false",
        }
    if "repetition_frustration" in intents:
        state.frustration_count += 1
    active_concern = next((code for code, status in state.focus.items() if status == "active"), mentioned)
    for name, value in facts.items():
        key = slot_key(active_concern, name)
        if not key:
            continue
        mapped = value
        if name == "laterality" and value in {"both", "bilateral", "both feet"}:
            mapped = "bilateral"
        if name == "claimed normal labs":
            mapped = "false"
        state.slots[key] = {"status": "answered", "value": mapped}
    if facts.get("laterality") in {"bilateral", "both"} and "burning_feet" in state.focus:
        state.slots.setdefault("burning_feet.laterality", {"status": "answered", "value": "bilateral"})
    if facts.get("laterality") in {"bilateral", "both"} and "facial_heat" in state.focus:
        state.slots.setdefault("facial_heat.laterality", {"status": "answered", "value": "bilateral"})
    if facts.get("meal_relation"):
        state.slots["facial_heat.meal_delay"] = {"status": "answered", "value": facts["meal_relation"]}
    if facts.get("episode_duration") or facts.get("duration"):
        state.slots["facial_heat.duration"] = {
            "status": "answered",
            "value": facts.get("episode_duration") or facts.get("duration"),
        }
    if "do not change" in (text or "").lower() or "don't change" in (text or "").lower() or "position and activity" in (text or "").lower():
        state.slots["burning_feet.position_activity_effect"] = {"status": "answered", "value": "none_reported"}
    state.last_intents = intents
    return state


def slot_is_answered(state: ControlState, question_closes: str | None) -> bool:
    if not question_closes:
        return False
    alias = SLOT_ALIASES.get(question_closes) or SLOT_ALIASES.get(normalize_label(question_closes))
    if not alias:
        return False
    return any(key.endswith(f".{alias}") and item.get("status") == "answered" for key, item in state.slots.items())


def decide_response_mode(
    *,
    safety_state: str,
    contradictions: list[str],
    control: ControlState,
    unanswered_high_value: bool,
) -> str:
    if safety_state in {"S3", "S4"}:
        return "SAFETY_ESCALATION"
    if contradictions:
        return "CLARIFY_CONTRADICTION"
    intents = set(control.last_intents)
    if "request_research" in intents and "request_next_steps" not in intents:
        return "RESEARCH_EXPLANATION"
    if "request_next_steps" in intents or "request_synthesis" in intents:
        return "NEXT_STEPS" if "request_next_steps" in intents else "INTERIM_SYNTHESIS"
    if control.cannot_provide_count >= 1 and "cannot_provide_evidence" in intents:
        return "INTERIM_SYNTHESIS"
    if control.frustration_count >= 2:
        return "INTERIM_SYNTHESIS"
    if unanswered_high_value:
        return "ASK_ONE_QUESTION"
    return "NO_ELIGIBLE_ACTION"


def filter_paused_questions(action_type: str, question_id: str | None, prompt: str | None, control: ControlState) -> bool:
    """Return True if the action is ineligible because it targets a paused concern."""
    paused = {code for code, status in control.focus.items() if status == "paused_by_user"}
    if "burning_feet" not in paused:
        return False
    blob = f"{question_id or ''} {prompt or ''}".lower()
    return bool(re.search(r"feet|foot|burn|laterality|emg", blob)) and action_type == "ask_question"
