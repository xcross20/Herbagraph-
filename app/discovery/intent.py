"""Classify user-turn intent. Multiple intents are allowed."""

from __future__ import annotations

import re

from app.discovery.conversation import parse_turn_answer

_INTENTS = (
    ("uncertainty", re.compile(r"\b(i don't know|dont know|not sure|unknown|idk)\b")),
    ("question", re.compile(r"\?|\bwhat (?:is|would|does|do)\b|\bwhy\b")),
    ("correction", re.compile(r"\bactually\b|\bi meant\b|\bno,? wait\b")),
    ("upload_reference", re.compile(r"\bupload\b|\battached\b|\breport\b")),
    ("request_summary", re.compile(r"\bsummar(?:y|ize)\b|\bwhat do you (?:know|have)\b")),
    ("stop", re.compile(r"\bstop\b|\benough questions\b|\bthat's all\b")),
    ("decline_question", re.compile(r"\bskip\b|\bdon't want to answer\b|\bpass\b")),
)

# Opening-door classifier for Ask vs labs vs stack (M09). Deterministic; does not diagnose.
_STACK_TERMS = re.compile(
    r"\b(berberine|red yeast|monacolin|cinnamon|olive leaf|oleuropein|"
    r"glucose disposal|i(?:['’]?m| am) (?:considering|starting|taking|buying))\b",
    re.I,
)
_LABS_ON_HAND = re.compile(
    r"\b(i already have labs|have (?:my )?labs|upload|pdf|quest|labcorp|mychart|healow)\b",
    re.I,
)
_INVESTIGATION = re.compile(
    r"\b(months?|years?|burning|numb|pain|pressure|ribs?|gallbladder|"
    r"feet|neuropathy|dizzy|fatigue|doctors? (?:said|say)|no one (?:knows|can))\b",
    re.I,
)
_DIAGNOSIS_DEMAND = re.compile(
    r"\b(what disease|what do i have|diagnose me|is this cancer)\b",
    re.I,
)


def classify_opening_door(text: str) -> str:
    """Return one of: labs_on_hand | stack_eval | investigation | diagnosis_demand | new_information."""
    lowered = (text or "").strip()
    if not lowered:
        return "new_information"
    if _DIAGNOSIS_DEMAND.search(lowered):
        return "diagnosis_demand"
    if _LABS_ON_HAND.search(lowered) and not _INVESTIGATION.search(lowered):
        return "labs_on_hand"
    if _STACK_TERMS.search(lowered) and not _INVESTIGATION.search(lowered):
        return "stack_eval"
    if _INVESTIGATION.search(lowered):
        return "investigation"
    if _LABS_ON_HAND.search(lowered):
        return "labs_on_hand"
    if _STACK_TERMS.search(lowered):
        return "stack_eval"
    return "new_information"


def classify_intent(text: str, *, current_question_closes: str | None = None) -> list[str]:
    lowered = (text or "").strip().lower()
    intents: list[str] = []
    if parse_turn_answer(text):
        intents.append("answer")
    if current_question_closes and lowered:
        intents.append("answer")
    for name, pattern in _INTENTS:
        if pattern.search(lowered) and name not in intents:
            intents.append(name)
    if not intents:
        intents.append("new_information")
    elif "answer" in intents and len(lowered.split()) > 6:
        intents.append("new_information")
    return intents
