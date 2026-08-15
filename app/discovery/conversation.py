"""Turn-based Discovery replies. Deterministic — the LLM does not speak here."""

from __future__ import annotations

from typing import Any

_YES = frozenset({"yes", "y", "yeah", "yep"})
_NO = frozenset({"no", "n", "nope", "not yet"})
_UNKNOWN = frozenset({"unknown", "not sure", "unsure", "idk", "i don't know", "dont know", "don't know"})


def parse_turn_answer(text: str) -> str | None:
    """Only a whole-message yes/no/unknown counts as answering the current question."""
    cleaned = " ".join((text or "").strip().lower().split()).rstrip(".!?")
    if cleaned in _YES:
        return "yes"
    if cleaned in _NO:
        return "no"
    if cleaned in _UNKNOWN:
        return "unknown"
    return None


def compose_system_reply(
    snapshot: Any,
    *,
    preface: str | None = None,
) -> tuple[str, str | None]:
    """One next question, or a stop. Never a diagnosis."""
    current = (snapshot.next_questions or [None])[0] if getattr(snapshot, "next_questions", None) else None
    chunks: list[str] = []
    if preface:
        chunks.append(preface)
    elif getattr(snapshot, "hypotheses", None) and current is not None:
        labels = ", ".join(item.label for item in snapshot.hypotheses[:2])
        chunks.append(f"Worth investigating: {labels}. That is not a diagnosis.")
    if current is not None:
        chunks.append(current.prompt)
        return " ".join(chunks), current.code
    chunks.append(
        "No more directed questions on this case. Add a note or labs if something new comes up. "
        "Still not a diagnosis."
    )
    return " ".join(chunks), None


def answer_preface(answer: str) -> str:
    if answer == "yes":
        return "Recorded as already assessed."
    if answer == "no":
        return "Recorded as not done. I will not keep asking this one."
    return "Noted as unknown. That gap stays open."
