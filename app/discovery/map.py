"""Versioned Investigation Map. Coverage is completeness, not disease probability."""

from __future__ import annotations

import hashlib
import json
from typing import Any


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


def build_map_payload(
    *,
    snapshot: Any,
    facts: dict[str, str],
    unknowns: list[str],
) -> dict:
    branches = []
    for hypo in snapshot.hypotheses:
        support = [
            f"{item.name}: {item.value}"
            for item in snapshot.findings
            if item.kind in {"symptom", "assessment"} and item.name not in {"safety_state"}
        ][:4]
        branches.append(
            {
                "code": hypo.code,
                "label": hypo.label,
                "relevance": hypo.investigation_relevance,
                "coverage": hypo.investigation_coverage,
                "certainty": hypo.diagnostic_certainty,
                "missing_markers": list(hypo.missing_markers or []),
                "not_a_diagnosis": hypo.not_a_diagnosis,
                "support": support,
                "against": [],
                "unknown": list(hypo.missing_markers or [])[:4],
                "why_here": (hypo.why_limited[0] if getattr(hypo, "why_limited", None) else hypo.not_a_diagnosis),
            }
        )
    increasers = confidence_increasers(
        facts=facts,
        unknowns=unknowns,
        hypotheses=snapshot.hypotheses,
        monitor_plan=getattr(snapshot, "monitor_plan", None),
    )
    return {
        "not_disease_probability": True,
        "investigation_coverage": snapshot.investigation_coverage,
        "branches": branches,
        "unknowns": list(unknowns),
        "confidence_increasers": increasers,
        "disclaimer": snapshot.disclaimer,
    }


def payload_fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
