"""Adaptive next questions. Deterministic — the LLM does not write these."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.discovery.utility import utility_for_marker


@dataclass(frozen=True)
class DiscoveryQuestion:
    code: str
    prompt: str
    kind: str
    closes: str
    hypothesis_code: str
    utility: float


_MARKER_PROMPTS: dict[str, str] = {
    "MMA": "Has methylmalonic acid (MMA) been measured?",
    "Homocysteine": "Has homocysteine been measured?",
    "HbA1c": "Has HbA1c been measured in the last 6 months?",
    "Insulin": "Has a fasting insulin been drawn?",
    "TSH": "Has TSH been checked recently?",
    "Free T4": "Has Free T4 been measured?",
    "EMG/NCS status": "Has EMG/nerve conduction testing already been done?",
    "Skin biopsy if exam and labs remain unexplained": "Has a skin biopsy for small-fiber neuropathy been discussed or done?",
    "Medication history (metformin, PPI)": "Is this person taking metformin, a PPI, or another B12-relevant medication?",
    "Focused neurologic / sensory exam": "Has a focused sensory / neurologic exam been documented?",
}


def next_questions(
    hypotheses: list[Any],
    *,
    limit: int = 5,
    answered: set[str] | None = None,
) -> list[DiscoveryQuestion]:
    answered_keys = {item.lower() for item in (answered or set())}
    questions: list[DiscoveryQuestion] = []
    seen: set[str] = set()
    for hypo in hypotheses[:4]:
        for marker in hypo.missing_markers:
            key = marker.lower()
            if key in seen or key in answered_keys:
                continue
            seen.add(key)
            questions.append(
                DiscoveryQuestion(
                    code=f"q_{hypo.code}_{key.replace(' ', '_')}",
                    prompt=_MARKER_PROMPTS.get(marker, f"Has {marker} already been assessed?"),
                    kind="already_tested",
                    closes=marker,
                    hypothesis_code=hypo.code,
                    utility=utility_for_marker(marker),
                )
            )
        for item in hypo.investigations:
            if item.already_assessed or item.group == "conditional":
                continue
            key = item.label.lower()
            if key in seen or key in answered_keys:
                continue
            seen.add(key)
            questions.append(
                DiscoveryQuestion(
                    code=f"q_{hypo.code}_{key.replace(' ', '_')[:40]}",
                    prompt=_MARKER_PROMPTS.get(item.label, f"Has this already been done: {item.label}?"),
                    kind="already_tested",
                    closes=item.label,
                    hypothesis_code=hypo.code,
                    utility=utility_for_marker(item.label),
                )
            )
        if len(questions) >= limit:
            break
    questions.sort(key=lambda q: q.utility, reverse=True)
    return questions[:limit]
