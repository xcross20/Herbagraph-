"""Compare two lab panels already stored for one person.

Movement is distance to the biomarker's own usual range.
A number moving is not a cause, and a missing later value is not "no change."
"""

from __future__ import annotations

from app.pipeline.manual_labs import normalize_typed_rows
from app.pipeline.response_analysis import compute_biomarker_change
from app.pipeline.safety_language import CLINICIAN, CONSUMER

DISCLAIMER = (
    "A lab moving is not proof that a supplement produced the change. "
    "A missing later value is not the same as no change."
)

_CLOSER = "improved"
_FARTHER = "worsened"
_STILL = "unchanged"
_UNKNOWN = "unknown"


def compare_lab_rows(baseline: list[dict], follow_up: list[dict], audience: str) -> dict:
    shown = audience if audience in {CONSUMER, CLINICIAN} else CONSUMER
    before = {row.biomarker_name: row for row in normalize_typed_rows(baseline)}
    after = {row.biomarker_name: row for row in normalize_typed_rows(follow_up)}
    changes = []
    for name in sorted(set(before) & set(after)):
        change = compute_biomarker_change(name, before[name].value, after[name].value, after[name].unit)
        changes.append(
            {
                "name": name,
                "direction": change["direction"],
                "baseline_value": change["baseline_value"],
                "follow_up_value": change["follow_up_value"],
                "text": _phrase(
                    name,
                    change["direction"],
                    change["baseline_value"],
                    change["follow_up_value"],
                    shown,
                ),
            }
        )
    missing = []
    for name in sorted(set(before) - set(after)):
        missing.append({"name": name, "side": "follow_up", "text": _missing(name, "later", shown)})
    for name in sorted(set(after) - set(before)):
        missing.append({"name": name, "side": "baseline", "text": _missing(name, "first", shown)})
    return {"audience": shown, "changes": changes, "missing": missing, "disclaimer": DISCLAIMER}


def _phrase(name: str, direction: str, baseline: float, follow_up: float, audience: str) -> str:
    before = _num(baseline)
    after = _num(follow_up)
    if audience == CLINICIAN:
        if direction == _CLOSER:
            return f"{name} is closer to its usual interval ({before} to {after}). Not a causal attribution."
        if direction == _FARTHER:
            return f"{name} is farther from its usual interval ({before} to {after}). Not a causal attribution."
        if direction == _STILL:
            return f"{name} is the same distance from its usual interval ({before}). Not evidence of no effect."
        return f"{name} has no usual interval on file, so direction is unknown."
    if direction == _CLOSER:
        return (
            f"{name} moved closer to the usual range ({before} to {after}). "
            "This is not proof that a supplement produced the change."
        )
    if direction == _FARTHER:
        return (
            f"{name} moved farther from the usual range ({before} to {after}). "
            "This is not proof that a supplement produced the change."
        )
    if direction == _STILL:
        return (
            f"{name} did not move relative to the usual range ({before}). "
            "This is not proof that a supplement had no effect."
        )
    return f"{name} was measured again. This check cannot tell whether that is closer to the usual range."


def _missing(name: str, which: str, audience: str) -> str:
    if audience == CLINICIAN:
        return f"{name} is absent from the {which} panel. Do not record that as unchanged."
    return f"{name} is missing from the {which} panel. Missing is not the same as no change."


def _num(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return str(number)
