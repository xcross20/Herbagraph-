"""Deterministic epistemic governor. The LLM proposes; this decides what may persist."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.coverage.evaluator import evaluate
from app.coverage.resolver import resolve_test
from app.discovery.ai import is_denied_concept


_RULED_OUT = re.compile(r"\b(ruled out|ruled-out|excluded|not neurological|nothing neurological)\b", re.I)
_DOCTOR_SAID = re.compile(r"\b(my doctor|the doctor|they said|was told|neurologist said)\b", re.I)
_IMBALANCE = re.compile(r"\b(biological imbalance|energy blockage|toxin dump|general imbalance)\b", re.I)
_SECONDS = re.compile(r"\b(\d+)\s*seconds?\b", re.I)
_CAUSAL = re.compile(r"\b(caused by|because of|from the|due to)\b", re.I)


@dataclass
class EpistemicDecision:
    allowed: bool
    severity: str = "info"
    reasons: list[str] = field(default_factory=list)
    required_tools: list[dict] = field(default_factory=list)
    modifications: list[dict] = field(default_factory=list)
    stored_text: str | None = None
    relation: str | None = None


class EpistemicValidator:
    def validate_finding(self, raw: str, *, concept: str = "", kind: str = "symptom") -> EpistemicDecision:
        text = (raw or "").strip()
        if not text:
            return EpistemicDecision(False, "error", ["empty finding"])
        if is_denied_concept(text) or is_denied_concept(concept):
            return EpistemicDecision(
                False,
                "block",
                ["denied diagnostic concept"],
                modifications=[{"action": "store_as_interpretation", "text": text}],
            )
        if _DOCTOR_SAID.search(text) and _RULED_OUT.search(text):
            return EpistemicDecision(
                True,
                "warn",
                ["clinician statement is reported, not verified rule-out"],
                required_tools=[{"tool": "REQUEST_RECORD", "reason": "Verify what was actually excluded."}],
                stored_text="Patient reports clinician said this was ruled out",
                modifications=[{"action": "downgrade_verification", "to": "reported"}],
            )
        return EpistemicDecision(True, "info", [], stored_text=text)

    def validate_interpretation(self, statement: str) -> EpistemicDecision:
        text = (statement or "").strip()
        if not text:
            return EpistemicDecision(False, "error", ["empty interpretation"])
        return EpistemicDecision(True, "info", ["kept as patient theory, not a finding"], stored_text=text)

    def validate_test_inference(self, raw_test: str, branch_concept: str, *, protocol: str | None = None) -> EpistemicDecision:
        match = resolve_test(raw_test, protocol)
        if match is None:
            return EpistemicDecision(
                True,
                "warn",
                ["unresolved test name"],
                required_tools=[{"tool": "GET_DOCUMENT", "reason": "Need the report to know what was tested."}],
                relation="inconclusive",
            )
        assessment = evaluate(match.test_code, branch_concept, match.protocol_code)
        if assessment.relation == "does_not_directly_assess":
            return EpistemicDecision(
                True,
                "warn",
                [assessment.explanation],
                relation=assessment.relation,
                modifications=[{"action": "do_not_close_branch", "branch": branch_concept}],
            )
        if match.protocol_code is None and assessment.coverage_confidence < 0.7:
            return EpistemicDecision(
                True,
                "warn",
                [assessment.explanation],
                required_tools=[{"tool": "GET_DOCUMENT", "reason": "Protocol changes coverage."}],
                relation=assessment.relation,
            )
        return EpistemicDecision(True, "info", [assessment.explanation], relation=assessment.relation)

    def validate_branch_resolution(self, *, relation: str | None, proposed_close: bool) -> EpistemicDecision:
        if proposed_close and relation in {None, "does_not_directly_assess", "inconclusive", "not_applicable"}:
            return EpistemicDecision(False, "block", ["coverage does not justify closing this branch"])
        return EpistemicDecision(True)

    def validate_mechanism_claim(self, text: str) -> EpistemicDecision:
        blob = text or ""
        seconds = _SECONDS.search(blob)
        if seconds and int(seconds.group(1)) <= 15 and _CAUSAL.search(blob):
            return EpistemicDecision(
                True,
                "warn",
                ["systemic causal attribution has low plausibility at this latency"],
                modifications=[{"action": "store_as_acute_sensation", "not": "efficacy"}],
            )
        if _IMBALANCE.search(blob):
            return EpistemicDecision(False, "block", ["unfalsifiable branch is not first-class"])
        return EpistemicDecision(True)

    def validate_correction(self, previous: str, replacement: str) -> EpistemicDecision:
        if not replacement.strip():
            return EpistemicDecision(False, "error", ["replacement is empty"])
        if previous.strip().lower() == replacement.strip().lower():
            return EpistemicDecision(False, "info", ["no material change"])
        return EpistemicDecision(
            True,
            "info",
            ["supersede prior event; do not invent a replacement theory"],
            modifications=[{"action": "supersede", "from": previous, "to": replacement}],
        )

    def validate_claim_strength(self, text: str) -> EpistemicDecision:
        lowered = (text or "").lower()
        if any(token in lowered for token in ("you have", "this confirms", "this proves", "definitely")):
            return EpistemicDecision(False, "block", ["over-strong claim"])
        return EpistemicDecision(True)


def clinician_rule_out_is_reported(text: str) -> bool:
    return bool(_DOCTOR_SAID.search(text or "") and _RULED_OUT.search(text or ""))


def gallbladder_split(text: str) -> dict[str, Any]:
    blob = (text or "").lower()
    if "gallbladder" not in blob:
        return {}
    return {
        "finding": {"concept": "abdominal_pain", "value": "location_unclear", "kind": "symptom"},
        "interpretation": {"statement": "Patient suspects gallbladder source", "concept": "biliary_source"},
    }
