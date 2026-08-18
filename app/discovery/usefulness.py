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

SAFETY_ACTIONS = frozenset({"show_safety_message", "advise_prompt_evaluation"})
SAFETY_QUESTION_IDS = frozenset({"q_weakness_safety"})
QUESTION_CONCERNS = {
    "q_laterality": "burning_feet",
    "q_distribution": "burning_feet",
    "q_temperature": "burning_feet",
    "q_emg": "burning_feet",
    "q_prior_workup": "burning_feet",
    "q_gi_location": "ruq_discomfort",
    "q_gi_episode": "ruq_discomfort",
    "q_gi_meal": "ruq_discomfort",
}

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

SLOT_PHRASES = (
    (re.compile(r"hour or more after|an hour or more after|>=\s*1 hour after"), "facial_heat.meal_delay", ">= 1 hour"),
    (re.compile(r"hour or two|60.?120 minutes|1.?2 hours"), "facial_heat.duration", "1-2 hours"),
    (re.compile(r"do not have the records|don'?t have (?:any )?(?:more )?(?:labs|records|those)"), "prior_labs.records_available", "false"),
    (re.compile(r"b12.{0,40}last year|last year.{0,40}b12|b12.{0,40}a year ago", re.I), "prior_labs.b12_last_check", "last_year"),
)

FAMILY_PAUSE_PATTERNS = (
    ("b12_functional_gap", re.compile(r"\bb12\b|cobalamin|one-carbon")),
    ("glucose_dysregulation", re.compile(r"\bglucose\b|a1c|blood sugar")),
)

FAMILY_CANDIDATE_IDS = {
    "b12_functional_gap": frozenset({"bf-b12", "bf-mma"}),
    "glucose_dysregulation": frozenset({"bf-glucose"}),
}

FAMILY_TARGETS = {
    "b12_functional_gap": "b12_status",
    "glucose_dysregulation": "glucose_regulation",
}


def usefulness_governor_enabled() -> bool:
    from app.config import get_settings

    settings = get_settings()
    env = (getattr(settings, "app_env", "") or "").lower()
    if env in {"uat", "preview"}:
        return True
    return bool(getattr(settings, "discovery_usefulness_governor_v1", False))


def load_usefulness_fixture(path: Path | None = None) -> dict:
    target = path or Path(__file__).resolve().parents[2] / "benchmarks" / "discovery_usefulness" / "v1" / "transcript.json"
    return json.loads(target.read_text(encoding="utf-8"))


def classify_control_intent(text: str) -> list[str]:
    blob = (text or "").lower()
    intents: list[str] = []
    if re.search(
        r"pause .{0,40}b12|never mind about b12|skip (?:the )?b12|don'?t (?:want to )?(?:deal with|talk about) .{0,20}b12",
        blob,
    ):
        intents.append("pause_family")
    if re.search(r"let'?s not deal with|don'?t (?:want to |wanna )?talk about|pause .{0,20}feet|skip the feet", blob):
        if "pause_family" not in intents:
            intents.append("pause_topic")
    if re.search(r"resume .{0,20}feet|back to (?:the )?feet|burning feet again", blob):
        intents.append("resume_topic")
    if re.search(
        r"what (?:do you think|should i do)|next step|what now|what else|plan|answers now|other insight|any other insight",
        blob,
    ):
        intents.append("request_next_steps")
    if re.search(r"what do you think|summar|assessment|so what is (?:this|going on)|answers now|other insight", blob):
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


def family_from_text(text: str) -> str | None:
    blob = (text or "").lower()
    for code, pattern in FAMILY_PAUSE_PATTERNS:
        if pattern.search(blob):
            return code
    return None


def _set_slot(state: ControlState, key: str, value: str) -> None:
    existing = state.slots.get(key)
    if existing and existing.get("status") == "answered":
        return
    state.slots[key] = {"status": "answered", "value": value}


def slot_key(concern: str | None, fact_name: str) -> str | None:
    alias = SLOT_ALIASES.get(fact_name) or SLOT_ALIASES.get(normalize_label(fact_name))
    if not alias:
        return None
    if fact_name == "duration" and concern == "facial_heat":
        return None
    scope = concern or "case"
    if fact_name in {"claimed normal labs", "emg testing"}:
        scope = "prior_labs" if "lab" in fact_name or fact_name.startswith("claimed") else "prior_labs"
    if fact_name == "emg testing":
        return "prior_labs.emg_status"
    if fact_name == "claimed normal labs":
        return "prior_labs.records_available"
    return f"{scope}.{alias}"


def parse_control_payload(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def paused_concerns(payload: dict | None) -> list[str]:
    focus = (payload or {}).get("focus") or {}
    return [code for code, status in focus.items() if status == "paused_by_user"]


def active_concerns(payload: dict | None) -> list[str]:
    focus = (payload or {}).get("focus") or {}
    return [code for code, status in focus.items() if status == "active"]


@dataclass
class ControlState:
    focus: dict[str, str] = field(default_factory=dict)
    paused_families: dict[str, str] = field(default_factory=dict)
    slots: dict[str, dict] = field(default_factory=dict)
    last_intents: list[str] = field(default_factory=list)
    focus_history: list[dict] = field(default_factory=list)
    applied_events: list[str] = field(default_factory=list)
    cannot_provide_count: int = 0
    frustration_count: int = 0
    version: int = 1

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "focus": dict(self.focus),
            "paused_families": dict(self.paused_families),
            "slots": dict(self.slots),
            "last_intents": list(self.last_intents),
            "focus_history": [dict(item) for item in self.focus_history],
            "applied_events": list(self.applied_events),
            "cannot_provide_count": self.cannot_provide_count,
            "frustration_count": self.frustration_count,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> ControlState:
        data = payload or {}
        return cls(
            focus=dict(data.get("focus") or {}),
            paused_families=dict(data.get("paused_families") or {}),
            slots=dict(data.get("slots") or {}),
            last_intents=list(data.get("last_intents") or []),
            focus_history=[dict(item) for item in (data.get("focus_history") or []) if isinstance(item, dict)],
            applied_events=[str(item) for item in (data.get("applied_events") or [])],
            cannot_provide_count=int(data.get("cannot_provide_count") or 0),
            frustration_count=int(data.get("frustration_count") or 0),
            version=int(data.get("version") or 1),
        )

    def paused_family_ids(self) -> set[str]:
        return {code for code, status in self.paused_families.items() if status == "paused_by_user"}


def _record_focus(
    state: ControlState,
    concern: str,
    new_state: str,
    *,
    reason: str,
    source_event_id: str | None,
) -> None:
    if source_event_id and any(
        item.get("source_event_id") == source_event_id
        and item.get("concern") == concern
        and item.get("state") == new_state
        for item in state.focus_history
    ):
        return
    prior = state.focus.get(concern)
    if prior == new_state:
        return
    state.focus[concern] = new_state
    state.focus_history.append(
        {
            "concern": concern,
            "state": new_state,
            "prior_state": prior,
            "reason": reason,
            "actor": "user",
            "source_event_id": source_event_id,
        }
    )


def apply_control(
    state: ControlState,
    text: str,
    facts: dict[str, str],
    source_event_id: str | None = None,
) -> ControlState:
    if source_event_id and source_event_id in state.applied_events:
        return state
    intents = classify_control_intent(text)
    mentioned = concern_from_text(text)
    if mentioned and mentioned not in state.focus:
        _record_focus(state, mentioned, "active", reason="mentioned", source_event_id=source_event_id)
    blob = (text or "").lower()
    if "facial" in blob or "heat" in blob:
        if "facial_heat" not in state.focus:
            _record_focus(state, "facial_heat", "active", reason="mentioned", source_event_id=source_event_id)
    if any(token in blob for token in ("rib", "gallbladder", "ruq")):
        if "ruq_discomfort" not in state.focus:
            _record_focus(state, "ruq_discomfort", "active", reason="mentioned", source_event_id=source_event_id)
    if any(token in blob for token in ("burn", "feet", "foot")):
        if "burning_feet" not in state.focus:
            _record_focus(state, "burning_feet", "active", reason="mentioned", source_event_id=source_event_id)
    if "pause_family" in intents:
        family = family_from_text(text) or "b12_functional_gap"
        if state.paused_families.get(family) != "paused_by_user":
            state.paused_families[family] = "paused_by_user"
            state.focus_history.append(
                {
                    "concern": family,
                    "state": "paused_by_user",
                    "prior_state": None,
                    "reason": "user_pause_family",
                    "actor": "user",
                    "source_event_id": source_event_id,
                }
            )
    elif "pause_topic" in intents:
        _record_focus(
            state,
            mentioned or "burning_feet",
            "paused_by_user",
            reason="user_pause",
            source_event_id=source_event_id,
        )
    if "resume_topic" in intents:
        _record_focus(
            state,
            mentioned or "burning_feet",
            "active",
            reason="user_resume",
            source_event_id=source_event_id,
        )
    if "cannot_provide_evidence" in intents:
        state.cannot_provide_count += 1
        _set_slot(state, "prior_labs.records_available", "false")
    if "repetition_frustration" in intents:
        state.frustration_count += 1
    if source_event_id:
        state.applied_events.append(source_event_id)
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
        _set_slot(state, key, mapped)
    if facts.get("laterality") in {"bilateral", "both"} and "burning_feet" in state.focus:
        _set_slot(state, "burning_feet.laterality", "bilateral")
    if facts.get("laterality") in {"bilateral", "both"} and "facial_heat" in state.focus:
        _set_slot(state, "facial_heat.laterality", "bilateral")
    if facts.get("meal_relation"):
        _set_slot(state, "facial_heat.meal_delay", facts["meal_relation"])
    if facts.get("episode_duration"):
        _set_slot(state, "facial_heat.duration", facts["episode_duration"])
    for pattern, key, value in SLOT_PHRASES:
        if pattern.search(text or ""):
            _set_slot(state, key, value)
    if re.search(r"inflamm", text or "", re.I):
        _set_slot(state, "patient_interpretation", facts.get("patient_interpretation") or "inflammatory foods")
    if "do not change" in (text or "").lower() or "don't change" in (text or "").lower() or "position and activity" in (text or "").lower():
        _set_slot(state, "burning_feet.position_activity_effect", "none_reported")
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


def concern_for_question(question_id: str | None, prompt: str | None) -> str | None:
    if question_id and question_id in QUESTION_CONCERNS:
        return QUESTION_CONCERNS[question_id]
    return concern_from_text(f"{question_id or ''} {prompt or ''}")


def filter_paused_questions(action_type: str, question_id: str | None, prompt: str | None, control: ControlState) -> bool:
    """Return True if the action is ineligible because it targets a paused concern."""
    if action_type in SAFETY_ACTIONS or question_id in SAFETY_QUESTION_IDS:
        return False
    if action_type != "ask_question":
        return False
    paused = {code for code, status in control.focus.items() if status == "paused_by_user"}
    if not paused:
        return False
    target = concern_for_question(question_id, prompt)
    return target in paused
