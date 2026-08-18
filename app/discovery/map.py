"""Versioned Investigation Map. Coverage is completeness, not disease probability."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.discovery.scientific_output import ScientificItem, ScientificItemType, validate_scientific_output


_PATTERN_UNKNOWNS = (
    "laterality",
    "distribution",
    "weakness",
    "temperature sensation",
    "emg testing",
)


def unknowns_from_facts(facts: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for key in _PATTERN_UNKNOWNS:
        value = facts.get(key)
        if value is None or value == "unknown":
            missing.append(key)
    return missing


def confidence_increasers(
    *,
    facts: dict[str, str],
    unknowns: list[str],
    hypotheses: list[Any],
    monitor_plan: list[Any] | None = None,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(label: str, reason: str) -> None:
        key = label.lower()
        if key in seen:
            return
        seen.add(key)
        items.append({"label": label, "reason": reason})

    if facts.get("claimed normal labs") == "unverified":
        _add("Upload the labs described as normal", "Recalled-normal results are unverified.")
    if facts.get("emg testing") in {"mentioned", "reported_normal", "reported_abnormal"}:
        _add("Verify the EMG / nerve-conduction report", "A recalled EMG does not say what was actually tested.")
    for name in unknowns:
        if name == "laterality":
            _add("Clarify laterality", "One-sided vs both feet changes which branches stay open.")
        elif name == "distribution":
            _add("Clarify how far the sensation extends", "Distal vs proximal changes sequencing.")
        elif name == "temperature sensation":
            _add("Ask whether temperature sensation is altered", "Supports whether small-fiber function is worth investigating.")
        elif name == "emg testing":
            _add("Ask whether EMG / NCS was already done", "Large-fiber testing status is unknown.")
        elif name == "weakness":
            _add("Confirm there is no new weakness", "Safety and branch selection both depend on this.")
    for hypo in hypotheses or []:
        for marker in list(getattr(hypo, "missing_markers", None) or [])[:2]:
            _add(f"Assess {marker}", f"Named gap on {getattr(hypo, 'label', 'an open family')}.")
    for item in (monitor_plan or [])[:3]:
        _add(getattr(item, "label", str(item)), getattr(item, "reason", "Next useful check."))
    return items[:8]


def _empty_evidence_buckets() -> dict[str, list]:
    return {
        "supports": [],
        "weakens": [],
        "does_not_address": [],
        "inconclusive": [],
        "unresolved": [],
        "contradictions": [],
    }


_TEST_FROM_FACT = {
    "emg testing": "emg_ncs",
}

_COVERAGE_PAIRS = {
    "small_fiber_dysfunction": (("emg_ncs", "small_fiber_density"),),
    "peripheral_nerve": (("emg_ncs", "small_fiber_density"),),
    "biliary_colic_pattern": (("emg_ncs", "biliary_stones"),),
    "biliary": (("emg_ncs", "biliary_stones"),),
}

_COVERAGE_USER_NOTES = {
    ("emg_ncs", "small_fiber_density"): (
        "A normal EMG does not assess small-fiber density.",
        "Small-fiber investigation remains open.",
    ),
    ("emg_ncs", "biliary_stones"): ("EMG is not evidence about biliary structure.",),
}


def _apply_scientific_output_gate(payload: dict[str, Any]) -> dict[str, Any]:
    notes = list(payload.get("coverage_notes") or [])
    accepted_notes: list[str] = []
    for note in notes:
        check = validate_scientific_output(
            [
                ScientificItem(
                    id="note",
                    version="1",
                    item_type=ScientificItemType.SYSTEM_INFERENCE,
                    statement=note,
                    provenance=list(payload.get("provenance") or ["coverage-governor-v1"]),
                )
            ],
            commerce_boosted=bool(payload.get("commerce_boosted")),
        )
        if check.accepted:
            accepted_notes.append(note)
    disclaimer = str(payload.get("disclaimer") or "")
    disclaimer_ok = True
    if disclaimer:
        disclaimer_ok = validate_scientific_output(
            [
                ScientificItem(
                    id="disclaimer",
                    version="1",
                    item_type=ScientificItemType.SYSTEM_INFERENCE,
                    statement=disclaimer,
                    provenance=["discovery-disclaimer"],
                )
            ]
        ).accepted
    gated = dict(payload)
    gated["coverage_notes"] = accepted_notes
    if not disclaimer_ok:
        gated["disclaimer"] = "This is not a diagnosis."
    gated["scientific_output_accepted"] = True
    gated.pop("scientific_output_violations", None)
    if len(accepted_notes) != len(notes) or not disclaimer_ok:
        from app.discovery.telemetry import increment

        increment("scientific_output_blocked")
    return gated


def _mentioned_tests(facts: dict[str, str]) -> set[str]:
    mentioned: set[str] = set()
    for name, test_code in _TEST_FROM_FACT.items():
        if facts.get(name) in {"mentioned", "reported_normal", "reported_abnormal"}:
            mentioned.add(test_code)
    return mentioned


def coverage_projection(
    *,
    facts: dict[str, str],
    hypotheses: list[Any],
    canonical_findings: list[Any] | None = None,
    safety_level: str = "S0",
) -> dict[str, Any]:
    """Structured coverage and user-facing notes from the governor + ranker."""
    from app.discovery.coverage_governor import assess_coverage
    from app.discovery.ranker import rank_next_actions

    mentioned = _mentioned_tests(facts)
    coverage: dict[str, dict[str, str]] = {}
    notes: list[str] = []
    provenance: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    for hypo in hypotheses or []:
        keys = (getattr(hypo, "code", None), getattr(hypo, "branch", None))
        for key in keys:
            for test_code, concept in _COVERAGE_PAIRS.get(key or "", ()):
                if test_code not in mentioned or (test_code, concept) in seen_pairs:
                    continue
                seen_pairs.add((test_code, concept))
                assessment = assess_coverage(test_code, concept)
                coverage.setdefault(test_code, {})[concept] = assessment.relation.value
                notes.extend(_COVERAGE_USER_NOTES.get((test_code, concept), ()))
                notes.append(assessment.explanation)
                provenance.append(assessment.rule_version)

    active = [item for item in (canonical_findings or []) if getattr(item, "active", True)]
    inactive = [item for item in (canonical_findings or []) if not getattr(item, "active", True)]
    active_names = {getattr(item, "name", None) for item in active}
    history = []
    for item in inactive:
        if getattr(item, "name", None) not in active_names:
            continue
        history.append(
            {
                "name": getattr(item, "name", None),
                "value": getattr(item, "value", None),
                "active": False,
            }
        )
    if any(item.get("name") == "onset" for item in history):
        current = next((item for item in active if getattr(item, "name", None) == "onset"), None)
        if current is not None:
            notes.append(f"current onset is {current.value}")
            notes.append("prior onset values remain in history")

    next_actions = [
        {"label": item.label, "explanation": item.explanation, "action_type": item.action_type}
        for item in rank_next_actions(gaps=[], safety_level=safety_level)
    ]
    return {
        "coverage": coverage,
        "coverage_notes": notes,
        "finding_history": history,
        "provenance": list(dict.fromkeys(provenance or ["coverage-governor-v1"])),
        "next_actions": next_actions,
        "commerce_boosted": False,
        "safety_level": safety_level,
    }


def build_map_payload(
    *,
    snapshot: Any,
    facts: dict[str, str],
    unknowns: list[str],
    evidence_by_branch: dict[str, dict[str, list]] | None = None,
    findings: list[Any] | None = None,
    canonical_findings: list[Any] | None = None,
    safety_level: str = "S0",
) -> dict:
    source_findings = [
        item
        for item in (findings if findings is not None else snapshot.findings)
        if getattr(item, "active", True)
    ]
    branches = []
    for hypo in snapshot.hypotheses:
        support = []
        for item in source_findings:
            kind = item.kind.value if hasattr(item.kind, "value") else item.kind
            if kind in {"symptom", "assessment"} and getattr(item, "name", None) not in {"safety_state"}:
                support.append(f"{item.name}: {item.value}")
            if len(support) == 4:
                break
        buckets = _empty_evidence_buckets()
        extra = (evidence_by_branch or {}).get(hypo.code) or {}
        for key in buckets:
            buckets[key] = list(extra.get(key) or [])
        branches.append(
            {
                "code": hypo.code,
                "label": hypo.label,
                "relevance": hypo.investigation_relevance,
                "coverage": hypo.investigation_coverage,
                "missing_markers": list(hypo.missing_markers or []),
                "not_a_diagnosis": hypo.not_a_diagnosis,
                "support": support,
                "against": list(buckets["weakens"]),
                "unknown": list(hypo.missing_markers or [])[:4],
                "why_here": (hypo.why_limited[0] if getattr(hypo, "why_limited", None) else hypo.not_a_diagnosis),
                **buckets,
            }
        )
    increasers = confidence_increasers(
        facts=facts,
        unknowns=unknowns,
        hypotheses=snapshot.hypotheses,
        monitor_plan=getattr(snapshot, "monitor_plan", None),
    )
    extra = coverage_projection(
        facts=facts,
        hypotheses=snapshot.hypotheses,
        canonical_findings=canonical_findings,
        safety_level=safety_level,
    )
    payload = {
        "not_disease_probability": True,
        "investigation_coverage": snapshot.investigation_coverage,
        "branches": branches,
        "unknowns": list(unknowns),
        "confidence_increasers": increasers,
        "disclaimer": snapshot.disclaimer,
        **extra,
    }
    return _apply_scientific_output_gate(payload)


def build_map_payload_v2(
    *,
    case_id: str,
    version: int,
    branches: list[dict],
    evidence: list[dict],
    gaps: list[dict],
) -> dict:
    """Serialize persistent branch state. No diagnostic probability."""
    by_branch: dict[str, list[dict]] = {}
    for item in evidence:
        by_branch.setdefault(str(item.get("branch_code") or ""), []).append(item)
    gaps_by_branch: dict[str, list[dict]] = {}
    for item in gaps:
        gaps_by_branch.setdefault(str(item.get("branch_code") or ""), []).append(item)
    rows = []
    counts = {"resolved_or_low_support": 0, "partially_evaluated": 0, "not_evaluated": 0}
    for branch in branches:
        code = branch.get("code") or ""
        status = branch.get("status") or "not_evaluated"
        if status in {"conditionally_resolved", "adequately_evaluated_no_support", "externally_confirmed"}:
            counts["resolved_or_low_support"] += 1
        elif status in {"partially_evaluated", "supported_for_further_investigation", "reopened"}:
            counts["partially_evaluated"] += 1
        else:
            counts["not_evaluated"] += 1
        links = by_branch.get(code, [])
        branch_gaps = gaps_by_branch.get(code, [])
        rows.append(
            {
                "id": branch.get("id"),
                "code": code,
                "label": branch.get("label"),
                "status": status,
                "relevance": "HIGH" if float(branch.get("investigation_relevance") or 0) >= 0.55 else "MODERATE",
                "coverage": branch.get("coverage") or 0,
                "coverage_confidence": branch.get("coverage_confidence") or 0,
                "supporting_evidence": [item for item in links if item.get("relationship") == "supports"],
                "weakening_evidence": [item for item in links if item.get("relationship") in {"weakens", "contradicts"}],
                "non_addressing_evidence": [item for item in links if item.get("relationship") == "does_not_address"],
                "resolved_gaps": [item for item in branch_gaps if item.get("status") == "resolved"],
                "open_gaps": [item for item in branch_gaps if item.get("status") != "resolved"],
                "next_best_evidence": [
                    {"label": item.get("label"), "reason": item.get("description") or "This would change the picture."}
                    for item in branch_gaps
                    if item.get("status") != "resolved"
                ][:3],
                "not_a_diagnosis": True,
            }
        )
    increasers = []
    for row in rows:
        for item in row["open_gaps"][:2]:
            increasers.append({"label": item.get("label") or "Open gap", "reason": item.get("description") or "Unresolved evidence gap."})
    return {
        "case_id": case_id,
        "version": version,
        "investigation_only": True,
        "summary": counts,
        "branches": rows,
        "confidence_increasers": increasers[:8],
        "disclaimer": "Investigation relevance is not a diagnosis. Coverage is completeness, not probability.",
    }


def payload_fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
