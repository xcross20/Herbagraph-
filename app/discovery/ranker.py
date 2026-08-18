"""Deterministic next-best investigation ranker (spec §26)."""

from __future__ import annotations

from dataclasses import dataclass

RANKER_VERSION = "ranker-v2"


@dataclass(frozen=True)
class RankedAction:
    action_type: str
    label: str
    branch_code: str | None
    gap_code: str | None
    score: float
    components: dict[str, float]
    explanation: str
    version: str = RANKER_VERSION
    rejected_reason: str | None = None
    alternatives: tuple[str, ...] = ()


def gap_is_ineligible(gap: dict) -> str | None:
    if gap.get("commerce_boosted"):
        return "commerce_cannot_change_scientific_rank"
    if gap.get("contraindicated"):
        return "contraindicated"
    if gap.get("completed") or gap.get("already_completed"):
        return "already_completed"
    if gap.get("non_addressing"):
        return "non_addressing"
    if gap.get("ineligible"):
        return "ineligible"
    if float(gap.get("redundancy") or 0.0) >= 1.0:
        return "redundant"
    return None


def _score_gap(gap: dict, index: int) -> tuple[float, dict[str, float]]:
    info = float(gap.get("information_value", 0.7))
    redundancy = float(gap.get("redundancy", 0.0))
    cost = float(gap.get("cost", 0.2))
    burden = float(gap.get("burden", 0.2))
    coverage_gain = float(gap.get("coverage_gain", info))
    safety = float(gap.get("safety", 0.0))
    score = max(
        0.0,
        0.45 * info
        + 0.30 * coverage_gain
        + 0.20 * safety
        - redundancy
        - 0.15 * cost
        - 0.15 * burden
        - index * 0.01,
    )
    return round(score, 4), {
        "safety": safety,
        "information_value": info,
        "coverage_gain": coverage_gain,
        "redundancy": redundancy,
        "cost": cost,
        "burden": burden,
    }


def rank_next_actions(
    *,
    gaps: list[dict],
    safety_level: str = "S0",
) -> list[RankedAction]:
    if safety_level in {"S3", "S4"}:
        return [
            RankedAction(
                action_type="professional_review",
                label="Seek urgent professional review",
                branch_code=None,
                gap_code=None,
                score=1.0,
                components={"safety": 1.0, "information_value": 0.0, "redundancy": 0.0},
                explanation="Safety override outranks investigation sequencing.",
            )
        ]
    eligible: list[tuple[int, dict]] = []
    rejected: list[RankedAction] = []
    for index, gap in enumerate(gaps):
        reason = gap_is_ineligible(gap)
        if reason:
            rejected.append(
                RankedAction(
                    action_type=str(gap.get("action_type") or "filtered"),
                    label=str(gap.get("label") or gap.get("code") or "filtered"),
                    branch_code=gap.get("branch_code"),
                    gap_code=gap.get("code"),
                    score=0.0,
                    components={"safety": 0.0},
                    explanation=reason,
                    rejected_reason=reason,
                )
            )
            continue
        eligible.append((index, gap))
    if not eligible:
        return [
            RankedAction(
                action_type="no_candidate",
                label="No remaining eligible investigation is available.",
                branch_code=None,
                gap_code=None,
                score=0.0,
                components={"safety": 0.0, "information_value": 0.0, "coverage_gain": 0.0},
                explanation="Every remaining candidate was ineligible, redundant, contraindicated, or non-addressing.",
            )
        ]
    ranked: list[RankedAction] = []
    for index, gap in eligible:
        score, components = _score_gap(gap, index)
        ranked.append(
            RankedAction(
                action_type=str(gap.get("action_type") or "clarifying_question"),
                label=str(gap.get("label") or gap.get("code") or "Clarify an open gap"),
                branch_code=gap.get("branch_code"),
                gap_code=gap.get("code"),
                score=score,
                components=components,
                explanation=str(gap.get("explanation") or "Highest-value remaining coverage gap."),
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.gap_code or "", item.label))
    if len(ranked) > 1:
        top = ranked[0]
        nxt = ranked[1]
        alternatives = tuple(
            f"{item.label} scored {item.score} (info={item.components.get('information_value')}, "
            f"coverage={item.components.get('coverage_gain')}, cost={item.components.get('cost')})"
            for item in ranked[1:3]
        )
        ranked[0] = RankedAction(
            action_type=top.action_type,
            label=top.label,
            branch_code=top.branch_code,
            gap_code=top.gap_code,
            score=top.score,
            components=top.components,
            explanation=(
                f"{top.explanation} Ranked above {nxt.label} because score {top.score} > {nxt.score}."
            ),
            alternatives=alternatives,
        )
    return ranked
