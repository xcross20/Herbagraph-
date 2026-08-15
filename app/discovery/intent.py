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
