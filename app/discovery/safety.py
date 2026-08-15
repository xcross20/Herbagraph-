"""Safety prescreen. Runs every turn. Deterministic — not a diagnosis."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyScreen:
    status: str
    reasons: tuple[str, ...]
    message: str


_URGENT = (
    (r"can'?t lift|cannot lift|foot drop", "new focal weakness"),
    (r"bladder|bowel control", "sphincter change"),
    (r"can'?t walk|cannot walk|falling", "severe gait change"),
)
_SUDDEN = re.compile(r"this morning|today|suddenly|sudden onset|started (?:this|today)")


def screen_safety(text: str) -> SafetyScreen:
    lowered = (text or "").lower()
    reasons = [label for pattern, label in _URGENT if re.search(pattern, lowered)]
    sudden = bool(_SUDDEN.search(lowered))
    if reasons and sudden:
        reasons = ["sudden onset", *reasons]
    if reasons:
        return SafetyScreen(
            status="urgent",
            reasons=tuple(reasons),
            message=(
                "This pattern — "
                + ", ".join(reasons)
                + " — is outside what HerbaGraph can organize as an outpatient investigation. "
                "Seek urgent in-person evaluation. This is not a diagnosis."
            ),
        )
    if sudden and re.search(r"weak|numb|burn", lowered):
        return SafetyScreen(
            status="watch",
            reasons=("sudden onset",),
            message=(
                "Sudden change is important. If weakness, collapse, or bladder/bowel change appears, "
                "stop here and seek urgent care. Otherwise I will keep organizing the investigation. "
                "This is not a diagnosis."
            ),
        )
    return SafetyScreen(status="routine", reasons=(), message="")
