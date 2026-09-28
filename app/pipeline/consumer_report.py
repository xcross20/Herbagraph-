"""Read a saved stack check in consumer or clinician words.

The stored verdict code is the fact. This module does not score again,
does not store a second copy, and does not treat a lab as a cause.
"""

from __future__ import annotations

import uuid

from app.models.enums import DiscoveryFindingKind
from app.pipeline.safety_language import (
    CLINICIAN,
    CONSUMER,
    known_phrase_ref,
    phrase_for_audience,
)

STACK_SOURCE = "stack_check"

DISCLAIMER = (
    "Not a diagnosis. This report does not call a result safe. "
    "A missing fact is not the same as safe."
)

_VERDICTS = frozenset({"hold", "food_first", "discuss", "mismatch", "unknown"})
_OUTSIDE = frozenset({"low", "high", "critical_low", "critical_high"})
_INSIDE = frozenset({"optimal", "normal"})

_GENERIC = {
    CONSUMER: {
        "hold": (
            "This item is on hold. This check does not call it safe, "
            "and it does not tell you to stop a prescribed medicine."
        ),
        "unknown": "A fact this check needed is missing. This check cannot treat that as safe.",
        "discuss": "This item matches a lab pattern. Discuss it with a clinician. This is not an instruction to start it.",
        "food_first": "This item is a food to discuss for this lab pattern. It is not a pill and not a prescription.",
        "mismatch": "These labs do not show the pattern this item is used for. That is not an instruction to take it.",
    },
    CLINICIAN: {
        "hold": "Hold. The stored check has no safety ref, so this reading does not name a mechanism.",
        "unknown": "A required safety fact is missing. Do not document the result as safe.",
        "discuss": "Discuss. This is not a directive to start the item.",
        "food_first": "Food-first. Not a pill substitute and not a prescription.",
        "mismatch": "The panel does not show this item's indication pattern. Not an instruction to take it.",
    },
}


def ref_for_verdict(verdict: dict) -> str | None:
    """The phrase key saved beside the verdict. Unknown keys are dropped."""
    for key in ("safety_refs", "missing_information"):
        values = verdict.get(key) or []
        if values and known_phrase_ref(values[0]):
            return values[0]
    return None


def build_case_report(*, case_id: uuid.UUID, findings, audience: str) -> dict:
    shown = audience if audience in {CONSUMER, CLINICIAN} else CONSUMER
    items = []
    labs = []
    for row in findings:
        if not getattr(row, "active", True):
            continue
        if _text(row, "source") != STACK_SOURCE:
            continue
        kind = _text(row, "kind")
        if kind == DiscoveryFindingKind.LAB.value:
            labs.append(_lab_line(row))
        elif kind == DiscoveryFindingKind.CONTEXT.value:
            item = _item_line(row, shown)
            if item is not None:
                items.append(item)
    return {
        "audience": shown,
        "case_id": case_id,
        "items": items,
        "labs": labs,
        "disclaimer": DISCLAIMER,
    }


def _item_line(row, audience: str) -> dict | None:
    verdict = _text(row, "value") or ""
    if verdict not in _VERDICTS:
        return None
    name = _text(row, "name") or ""
    code = _text(row, "branch")
    ref = _ref_from_event(getattr(row, "source_event_id", None))
    phrase_row = {
        "name": name,
        "verdict": verdict,
        "code": code,
        "reason": _GENERIC[audience][verdict],
        "safety_refs": [ref] if ref and ref not in {"current medications", "pregnancy status", "unrecognized medication"} else [],
        "missing_information": [ref] if ref in {"current medications", "pregnancy status", "unrecognized medication"} else [],
    }
    return {"name": name, "verdict": verdict, "text": phrase_for_audience(phrase_row, audience)}


def _lab_line(row) -> dict:
    name = _text(row, "name") or "Lab"
    status = (_text(row, "status") or "").lower()
    if status in _OUTSIDE:
        text = f"{name} is outside the usual range."
    elif status in _INSIDE:
        text = f"{name} is inside the usual range."
    else:
        text = f"{name} was recorded. This report does not grade it."
    return {"name": name, "status": status, "text": text}


def _ref_from_event(source_event_id: str | None) -> str | None:
    prefix = f"{STACK_SOURCE}:"
    if not source_event_id or not source_event_id.startswith(prefix):
        return None
    ref = source_event_id[len(prefix):]
    return ref if known_phrase_ref(ref) else None


def _text(row, name: str) -> str | None:
    raw = getattr(row, name, None)
    if raw is None:
        return None
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw)
