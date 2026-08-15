"""Deterministic fact extraction. Every user turn is free-text evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.discovery.engine import FindingDraft


@dataclass(frozen=True)
class ExtractedFact:
    name: str
    value: str
    kind: str = "symptom"


_RULES: tuple[tuple[str, str, str], ...] = (
    (r"\bburn(?:ed|ing)?\b", "burning sensation", "reported"),
    (r"\btingl|\bpins and needles\b", "paresthesia", "reported"),
    (r"\bnumb", "numbness", "reported"),
    (r"hot.{0,12}cold|temperature", "temperature sensation", "altered"),
    (r"\bfeet\b|\bfoot\b", "location", "feet"),
    (r"\btoes?\b|\bsoles?\b", "distribution", "distal"),
    (r"above (?:the )?ankles?|into (?:the )?legs?", "distribution", "proximal_extension"),
    (r"both feet|both sides|bilateral", "laterality", "bilateral"),
    (r"right (?:is )?worse|worse on the right", "laterality", "bilateral_right_greater"),
    (r"left (?:is )?worse|worse on the left", "laterality", "bilateral_left_greater"),
    (r"only (?:my )?right|mainly (?:the |my )?right|right foot only", "laterality", "right"),
    (r"only (?:my )?left|mainly (?:the |my )?left|left foot only", "laterality", "left"),
    (r"\bat night\b|\bnightly\b|\bmidnight\b|nocturnal", "timing", "nighttime"),
    (r"six months|6 months", "duration", "about 6 months"),
    (r"this morning|today|suddenly|sudden onset", "onset", "sudden"),
    (r"can'?t lift|cannot lift|foot drop|new weakness", "weakness", "reported"),
    (r"\bbladder\b|\bbowel control\b", "sphincter change", "reported"),
    (r"blood work is normal|labs? (?:were |are )?normal", "claimed normal labs", "unverified"),
    (r"\bemg\b|nerve conduction|\bncs\b", "emg testing", "mentioned"),
)


_LATERALITY_OPTIONS = {
    "left": "left",
    "right": "right",
    "both": "bilateral",
    "changes sides": "alternating",
    "not sure": "unknown",
}


def extract_facts(text: str, *, current_question_closes: str | None = None) -> list[ExtractedFact]:
    raw = text or ""
    lowered = raw.lower()
    facts: list[ExtractedFact] = []
    seen: set[str] = set()

    def _add(name: str, value: str, kind: str = "symptom") -> None:
        key = f"{name}:{value}"
        if key in seen:
            return
        seen.add(key)
        facts.append(ExtractedFact(name=name, value=value, kind=kind))

    for pattern, name, value in _RULES:
        if re.search(pattern, lowered):
            kind = "assessment" if name in {"emg testing", "claimed normal labs"} else "symptom"
            _add(name, value, kind)

    option = _LATERALITY_OPTIONS.get(lowered.strip().rstrip(".!"))
    if option and (current_question_closes == "laterality" or option):
        if current_question_closes == "laterality" or option in {"left", "right", "bilateral", "alternating", "unknown"}:
            if current_question_closes == "laterality":
                _add("laterality", option)

    if current_question_closes == "emg_status":
        if re.search(r"\bnormal\b", lowered):
            _add("emg testing", "reported_normal", "assessment")
        elif re.search(r"\babnormal\b|\bpositive\b", lowered):
            _add("emg testing", "reported_abnormal", "assessment")

    if current_question_closes == "laterality" and re.search(r"\bboth\b", lowered) and re.search(r"\bright\b", lowered):
        _add("laterality", "bilateral_right_greater")

    return facts


def facts_to_findings(facts: list[ExtractedFact]) -> list[FindingDraft]:
    return [
        FindingDraft(
            kind=item.kind,
            name=item.name,
            value=item.value,
            status=None,
            branch=None,
            source="intake",
        )
        for item in facts
    ]


def fact_map(findings: list[FindingDraft]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for item in findings:
        if item.name:
            mapped[item.name] = item.value or "reported"
    return mapped


def problem_representation(facts: dict[str, str]) -> str:
    parts: list[str] = []
    if facts.get("duration"):
        parts.append(f"Duration {facts['duration']}")
    if facts.get("onset") == "sudden":
        parts.append("sudden onset")
    if facts.get("burning sensation"):
        loc = facts.get("location", "unspecified site")
        timing = facts.get("timing")
        chunk = f"burning sensation affecting the {loc}"
        if timing:
            chunk += f", {timing}"
        parts.append(chunk)
    if facts.get("laterality"):
        parts.append(f"laterality {facts['laterality'].replace('_', ' ')}")
    else:
        parts.append("laterality unknown")
    if facts.get("distribution"):
        parts.append(f"distribution {facts['distribution'].replace('_', ' ')}")
    if facts.get("temperature sensation"):
        parts.append("temperature sensation altered")
    if facts.get("weakness") == "reported":
        parts.append("weakness reported")
    else:
        parts.append("weakness not established")
    if facts.get("claimed normal labs"):
        parts.append("prior labs described as normal (unverified)")
    if not parts:
        return "Problem representation is not yet complete."
    text = "; ".join(parts) + "."
    return text[0].upper() + text[1:]


def detect_contradictions(prior: dict[str, str], incoming: list[ExtractedFact]) -> list[str]:
    contradictions: list[str] = []
    for fact in incoming:
        previous = prior.get(fact.name)
        if not previous or previous == fact.value:
            continue
        if fact.name == "laterality" and previous != fact.value and "unknown" not in {previous, fact.value}:
            sides = {previous, fact.value}
            if sides & {"left", "right"} and sides & {"bilateral", "bilateral_right_greater", "bilateral_left_greater"}:
                contradictions.append("laterality")
            elif previous != fact.value and fact.name == "laterality":
                contradictions.append("laterality")
    return contradictions
