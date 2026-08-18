"""Deterministic next-best investigation ranker (spec §26)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedAction:
    action_type: str
    label: str
    branch_code: str | None
    gap_code: str | None
    score: float
    components: dict[str, float]
    explanation: str
    version: str = "ranker-v1"


def rank_next_actions(
    *,
    gaps: list[dict],
    safety_level: str = "S0",
) -> list[RankedAction]:
    ranked: list[RankedAction] = []
    if safety_level in {"S3", "S4"}:
        ranked.append(
            RankedAction(
                action_type="professional_review",
                label="Seek urgent professional review",
                branch_code=None,
                gap_code=None,
                score=1.0,
                components={"safety": 1.0, "information_value": 0.0, "redundancy": 0.0},
                explanation="Safety override outranks investigation sequencing.",
            )
        )
        return ranked
    for index, gap in enumerate(gaps):
        info = float(gap.get("information_value", 0.7))
        redundancy = float(gap.get("redundancy", 0.0))
        cost = float(gap.get("cost", 0.2))
        burden = float(gap.get("burden", 0.2))
        coverage_gain = float(gap.get("coverage_gain", info))
        score = max(
            0.0,
            0.45 * info
            + 0.30 * coverage_gain
            - redundancy
            - 0.15 * cost
            - 0.15 * burden
            - index * 0.01,
        )
        ranked.append(
            RankedAction(
                action_type=str(gap.get("action_type") or "clarifying_question"),
                label=str(gap.get("label") or gap.get("code") or "Clarify an open gap"),
                branch_code=gap.get("branch_code"),
                gap_code=gap.get("code"),
                score=round(score, 4),
                components={
                    "safety": 0.0,
                    "information_value": info,
                    "coverage_gain": coverage_gain,
                    "redundancy": redundancy,
                    "cost": cost,
                    "burden": burden,
                },
                explanation=str(gap.get("explanation") or "Highest-value remaining coverage gap."),
            )
        )
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked
