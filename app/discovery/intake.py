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
    (r"(?<!gall )\bbladder\b|\bbowel control\b", "sphincter change", "reported"),
    (r"blood work is normal|labs? (?:were |are )?normal", "claimed normal labs", "unverified"),
    (r"\bemg\b|nerve conduction|\bncs\b", "emg testing", "mentioned"),
    (r"feel like throwing up|nauseous|nauseat|queasy|\bnausea\b", "nausea", "reported"),
    (r"can eat fat|eat fat but|fatty food (?:is )?(?:fine|ok|okay)", "fatty_food", "tolerated"),
    (r"fatty food makes|worse after (?:fatty|greasy)|can't (?:eat|tolerate) fat", "fatty_food", "triggers"),
    (r"\bintermittent\b|comes and goes", "trajectory", "intermittent"),
    (r"under (?:the |my )?(?:right )?ribs|right upper|\bruq\b", "location", "ruq"),
    (r"pit of (?:the )?stomach|epigastric", "location", "epigastric"),
    (r"\bitch|\bitches\b|itchy", "itch", "reported"),
    (r"crawl|creepy.?crawly", "crawling_sensation", "reported"),
    (r"reproduct|genital|groin", "itch_site", "reproductive_or_genital_area"),
    (r"\bpopcorn\b", "popcorn_association", "reported"),
    (r"juice fast|fasting.{0,20}juice|juice.{0,20}fast", "juice_fasting_association", "improves"),
    (r"shoulder", "shoulder_pain", "reported"),
    (r"no (?:visible )?swell|without swell|not swell", "visible_swelling", "absent"),
    (r"no redness|without redness|not red", "visible_redness", "absent"),
    (r"no warmth|not warm|without warmth", "visible_warmth", "absent"),
    (r"after (?:burgers|fries|a meal|eating)|tied to eating|after meals", "meal_relation", "after_eating"),
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
            if name == "location" and value == "epigastric" and re.search(r"rib|ruq|right upper", lowered):
                continue
            kind = "assessment" if name in {"emg testing", "claimed normal labs", "swelling", "redness", "warmth"} else "symptom"
            _add(name, value, kind)
    if re.search(r"no (?:visible )?swell", lowered):
        _add("visible_swelling", "absent", "assessment")
        if "redness" in lowered:
            _add("visible_redness", "absent", "assessment")
        if "warmth" in lowered:
            _add("visible_warmth", "absent", "assessment")
    if re.search(r"no (?:visible )?(?:swell|redness|warmth)", lowered):
        if "swell" in lowered:
            _add("visible_swelling", "absent")
        if "redness" in lowered or "red" in lowered:
            _add("visible_redness", "absent")
        if "warmth" in lowered or "warm" in lowered:
            _add("visible_warmth", "absent")
    if any(item.name == "location" and item.value == "ruq" for item in facts):
        facts[:] = [item for item in facts if not (item.name == "location" and item.value == "epigastric")]

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


def is_abdominal_case(facts: dict[str, str]) -> bool:
    if facts.get("abdominal_pain") or facts.get("nausea"):
        return True
    if facts.get("location") in {"ruq", "abdomen", "epigastric"}:
        return True
    if facts.get("fatty_food"):
        return True
    blob = " ".join(f"{key} {value}" for key, value in facts.items()).lower()
    return "gallbladder" in blob or "biliary" in blob


def fact_map(findings: list[FindingDraft]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for item in findings:
        if not item.name:
            continue
        if item.name == "location" and mapped.get("location") == "ruq" and item.value == "epigastric":
            mapped["location_secondary"] = item.value or "epigastric"
            continue
        mapped[item.name] = item.value or "reported"
    return mapped


def problem_representation(facts: dict[str, str]) -> str:
    if is_abdominal_case(facts):
        return _abdominal_representation(facts)
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


def _abdominal_representation(facts: dict[str, str]) -> str:
    parts: list[str] = []
    if facts.get("abdominal_pain"):
        parts.append(f"abdominal sensation ({facts['abdominal_pain'].replace('_', ' ')})")
    if facts.get("location") in {"ruq", "epigastric", "abdomen"}:
        parts.append(f"felt at {facts['location']}")
    if facts.get("nausea"):
        parts.append("nausea reported")
    if facts.get("vomiting") == "absent":
        parts.append("vomiting absent")
    elif facts.get("vomiting"):
        parts.append(f"vomiting {facts['vomiting']}")
    if facts.get("fatty_food") == "tolerated":
        parts.append("can eat fat")
    elif facts.get("fatty_food") == "triggers":
        parts.append("worse after fatty food")
    if facts.get("trajectory"):
        parts.append(f"trajectory {facts['trajectory'].replace('_', ' ')}")
    if facts.get("fever") == "absent":
        parts.append("no fever")
    interps = [value for key, value in facts.items() if key.startswith("patient_interpretation") and value]
    if interps:
        parts.append(f"patient theory: {interps[0]} (not a finding)")
    if not parts:
        return "Abdominal or nausea pattern is not yet fully characterized."
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
