"""Rebuild Case state from a presenting concern + labs + profile.

The Case — not the chat transcript — is the source of truth. This module is
pure and deterministic. The LLM must not write findings or close hypotheses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.discovery.catalog import (
    BRANCH_LABELS,
    HYPOTHESIS_FAMILIES,
    HypothesisFamily,
    families_for_concern,
)
from app.discovery.questions import DiscoveryQuestion, next_questions
from app.evidence_confidence.resolution_markers import (
    marker_is_present,
    present_marker_keys,
)
from app.models.enums import LabResultStatus
from app.schemas.pipeline import NormalizedLabResult

_ABNORMAL = frozenset(
    {
        LabResultStatus.LOW,
        LabResultStatus.HIGH,
        LabResultStatus.CRITICAL_LOW,
        LabResultStatus.CRITICAL_HIGH,
    }
)

# Certainty stays below a diagnosis even with a full panel.
MAX_DIAGNOSTIC_CERTAINTY = 0.55
MAX_CERTAINTY_WITH_SUPPORT = 0.72


@dataclass
class FindingDraft:
    kind: str
    name: str
    value: str | None
    status: str | None
    branch: str | None
    source: str


@dataclass
class InvestigationItem:
    label: str
    group: str
    already_assessed: bool


@dataclass
class HypothesisDraft:
    code: str
    label: str
    branch: str
    investigation_relevance: float
    diagnostic_certainty: float
    investigation_coverage: float
    status: str
    why_limited: list[str]
    missing_markers: list[str]
    investigations: list[InvestigationItem]
    not_a_diagnosis: str


@dataclass
class BranchCoverage:
    branch: str
    label: str
    coverage: float
    assessed: int
    expected: int


@dataclass
class MonitorItem:
    """Next useful check — not a hunt to 90% confidence."""

    label: str
    group: str
    hypothesis_code: str
    reason: str


@dataclass
class CaseSnapshot:
    presenting_concern: str
    findings: list[FindingDraft]
    hypotheses: list[HypothesisDraft]
    branch_coverage: list[BranchCoverage]
    investigation_coverage: float
    monitor_plan: list[MonitorItem] = field(default_factory=list)
    next_questions: list[DiscoveryQuestion] = field(default_factory=list)
    what_changed: list[str] = field(default_factory=list)
    disclaimer: str = field(
        default="Investigation relevance is not a diagnosis. "
        "HerbaGraph does not claim the person has any listed condition."
    )

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> CaseSnapshot:
        findings = [FindingDraft(**item) for item in raw.get("findings") or []]
        hypotheses = []
        for item in raw.get("hypotheses") or []:
            investigations = [InvestigationItem(**inv) for inv in item.get("investigations") or []]
            payload = {**item, "investigations": investigations}
            hypotheses.append(HypothesisDraft(**payload))
        branches = [BranchCoverage(**item) for item in raw.get("branch_coverage") or []]
        monitor = [MonitorItem(**item) for item in raw.get("monitor_plan") or []]
        questions = [DiscoveryQuestion(**item) for item in raw.get("next_questions") or []]
        return cls(
            presenting_concern=raw.get("presenting_concern") or "",
            findings=findings,
            hypotheses=hypotheses,
            branch_coverage=branches,
            investigation_coverage=float(raw.get("investigation_coverage") or 0.0),
            monitor_plan=monitor,
            next_questions=questions,
            what_changed=list(raw.get("what_changed") or []),
            disclaimer=raw.get("disclaimer")
            or "Investigation relevance is not a diagnosis. "
            "HerbaGraph does not claim the person has any listed condition.",
        )


def _status_enum(status: str | LabResultStatus | None) -> LabResultStatus | None:
    if status is None:
        return None
    if isinstance(status, LabResultStatus):
        return status
    try:
        return LabResultStatus(str(status))
    except ValueError:
        return None


def _is_abnormal(status: str | LabResultStatus | None) -> bool:
    parsed = _status_enum(status)
    return parsed in _ABNORMAL if parsed else False


def findings_from_inputs(
    presenting_concern: str,
    labs: list[NormalizedLabResult],
    health_profile: dict | None = None,
) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    concern = (presenting_concern or "").strip()
    if concern:
        findings.append(
            FindingDraft(
                kind="concern",
                name="Presenting concern",
                value=concern,
                status=None,
                branch=None,
                source="user",
            )
        )
    profile = health_profile or {}
    for key, label in (
        ("age_range", "Age"),
        ("biological_sex", "Biological sex"),
        ("current_medications", "Medications"),
        ("known_conditions", "Prior diagnoses"),
        ("current_supplements", "Supplements"),
        ("presenting_symptoms", "Recorded symptoms"),
    ):
        value = profile.get(key)
        if not value:
            continue
        text = ", ".join(value) if isinstance(value, list) else str(value)
        findings.append(
            FindingDraft(
                kind="context",
                name=label,
                value=text,
                status=None,
                branch=None,
                source="profile",
            )
        )
    for lab in labs:
        findings.append(
            FindingDraft(
                kind="lab",
                name=lab.biomarker_name,
                value=f"{lab.value}{(' ' + lab.unit) if lab.unit else ''}".strip(),
                status=lab.status.value if hasattr(lab.status, "value") else str(lab.status),
                branch=None,
                source="lab_engine",
            )
        )
    return findings


def _lab_names(labs: list[NormalizedLabResult]) -> list[str]:
    return [lab.biomarker_name for lab in labs]


def _abnormal_names(labs: list[NormalizedLabResult]) -> set[str]:
    return {lab.biomarker_name for lab in labs if _is_abnormal(lab.status)}


def _coverage_for_markers(markers: tuple[str, ...], present_keys: set[str]) -> tuple[float, list[str], int, int]:
    if not markers:
        return 0.0, [], 0, 0
    missing = [marker for marker in markers if not marker_is_present(marker, present_keys)]
    assessed = len(markers) - len(missing)
    return assessed / len(markers), missing, assessed, len(markers)


def _score_family(
    family: HypothesisFamily,
    *,
    concern_hit: bool,
    labs: list[NormalizedLabResult],
) -> HypothesisDraft:
    present_keys = present_marker_keys(_lab_names(labs))
    abnormal_keys = present_marker_keys(list(_abnormal_names(labs)))
    support_hits = sum(1 for marker in family.supporting_markers if marker_is_present(marker, abnormal_keys))
    coverage, missing, _assessed, _expected = _coverage_for_markers(family.resolution_markers, present_keys)

    relevance = 0.0
    if concern_hit:
        relevance += 0.42
    relevance += min(0.40, 0.18 * support_hits)
    if coverage >= 0.5:
        relevance += 0.08
    relevance = min(relevance, 0.95)

    certainty = 0.12 if concern_hit else 0.05
    certainty += min(0.28, 0.12 * support_hits)
    if coverage >= 1.0 and support_hits:
        certainty += 0.10
    if support_hits == 0:
        certainty = min(certainty, 0.28)
    else:
        certainty = min(certainty, MAX_CERTAINTY_WITH_SUPPORT)
    certainty = min(certainty, MAX_DIAGNOSTIC_CERTAINTY if support_hits < 2 else certainty)

    why_limited: list[str] = []
    if support_hits == 0:
        why_limited.append("No confirmatory abnormal labs for this family yet.")
    if missing:
        why_limited.append("Missing: " + ", ".join(missing[:5]))
    why_limited.append(family.why_not_a_diagnosis)

    investigations: list[InvestigationItem] = []
    for group, items in (
        ("core", family.core),
        ("directed", family.directed),
        ("conditional", family.conditional),
    ):
        for item in items:
            assessed = marker_is_present(item, present_keys)
            investigations.append(InvestigationItem(label=item, group=group, already_assessed=assessed))

    return HypothesisDraft(
        code=family.code,
        label=family.label,
        branch=family.branch,
        investigation_relevance=round(relevance, 4),
        diagnostic_certainty=round(min(certainty, MAX_DIAGNOSTIC_CERTAINTY if support_hits < 2 else certainty), 4),
        investigation_coverage=round(coverage, 4),
        status="open",
        why_limited=why_limited,
        missing_markers=missing,
        investigations=investigations,
        not_a_diagnosis=family.why_not_a_diagnosis,
    )


def _families_to_score(concern: str, labs: list[NormalizedLabResult]) -> list[tuple[HypothesisFamily, bool]]:
    from_concern = {family.code: family for family in families_for_concern(concern)}
    abnormal = _abnormal_names(labs)
    abnormal_keys = present_marker_keys(list(abnormal))
    selected: dict[str, tuple[HypothesisFamily, bool]] = {
        code: (family, True) for code, family in from_concern.items()
    }
    for family in HYPOTHESIS_FAMILIES:
        if family.code in selected:
            continue
        if any(marker_is_present(marker, abnormal_keys) for marker in family.supporting_markers):
            selected[family.code] = (family, False)
    return list(selected.values())


def _branch_coverage(hypotheses: list[HypothesisDraft], labs: list[NormalizedLabResult]) -> list[BranchCoverage]:
    present_keys = present_marker_keys(_lab_names(labs))
    by_branch: dict[str, list[HypothesisDraft]] = {}
    for hypo in hypotheses:
        by_branch.setdefault(hypo.branch, []).append(hypo)
    rows: list[BranchCoverage] = []
    for branch, items in sorted(by_branch.items()):
        markers: list[str] = []
        for hypo in items:
            family = next((f for f in HYPOTHESIS_FAMILIES if f.code == hypo.code), None)
            if family:
                markers.extend(family.resolution_markers)
        unique = tuple(dict.fromkeys(markers))
        coverage, _missing, assessed, expected = _coverage_for_markers(unique, present_keys)
        rows.append(
            BranchCoverage(
                branch=branch,
                label=BRANCH_LABELS.get(branch, branch.replace("_", " ").title()),
                coverage=round(coverage, 4),
                assessed=assessed,
                expected=expected,
            )
        )
    return rows


def _monitor_plan(hypotheses: list[HypothesisDraft]) -> list[MonitorItem]:
    plan: list[MonitorItem] = []
    seen: set[str] = set()

    def _add(label: str, group: str, hypo: HypothesisDraft) -> bool:
        key = label.lower()
        if key in seen:
            return False
        seen.add(key)
        plan.append(
            MonitorItem(
                label=label,
                group=group,
                hypothesis_code=hypo.code,
                reason=f"Would change what we do next on {hypo.label}.",
            )
        )
        return len(plan) >= 6

    for hypo in hypotheses[:4]:
        for marker in hypo.missing_markers:
            if _add(marker, "directed", hypo):
                return plan
    for group in ("core", "directed"):
        for hypo in hypotheses[:4]:
            for item in hypo.investigations:
                if item.group != group or item.already_assessed:
                    continue
                if _add(item.label, group, hypo):
                    return plan
    return plan


def rebuild_case_state(
    presenting_concern: str,
    labs: list[NormalizedLabResult] | None = None,
    health_profile: dict | None = None,
) -> CaseSnapshot:
    labs = labs or []
    findings = findings_from_inputs(presenting_concern, labs, health_profile)
    scored = [_score_family(family, concern_hit=hit, labs=labs) for family, hit in _families_to_score(presenting_concern, labs)]
    scored.sort(key=lambda item: (item.investigation_relevance, item.investigation_coverage), reverse=True)
    branches = _branch_coverage(scored, labs)
    if branches:
        overall = sum(row.coverage for row in branches) / len(branches)
    else:
        overall = 0.0
    snapshot = CaseSnapshot(
        presenting_concern=(presenting_concern or "").strip(),
        findings=findings,
        hypotheses=scored,
        branch_coverage=branches,
        investigation_coverage=round(overall, 4),
        monitor_plan=_monitor_plan(scored),
    )
    snapshot.next_questions = next_questions(snapshot.hypotheses)
    return snapshot


def describe_rebuild_changes(previous: CaseSnapshot | None, current: CaseSnapshot) -> list[str]:
    """Evidence reconciliation: what the new snapshot added or resolved."""
    if previous is None:
        if current.hypotheses:
            return [f"Opened {len(current.hypotheses)} investigation families from the current concern and data."]
        return ["Case opened. No investigation families activated yet."]
    changes: list[str] = []
    prev_codes = {item.code for item in previous.hypotheses}
    new_codes = {item.code for item in current.hypotheses}
    for code in sorted(new_codes - prev_codes):
        label = next(item.label for item in current.hypotheses if item.code == code)
        changes.append(f"New investigation family: {label}.")
    prev_findings = {(item.kind, item.name, item.value) for item in previous.findings}
    for item in current.findings:
        key = (item.kind, item.name, item.value)
        if key not in prev_findings and item.kind == "lab":
            changes.append(
                f"New lab finding: {item.name} {item.value or ''} ({item.status or 'recorded'}).".strip()
            )
    if current.investigation_coverage != previous.investigation_coverage:
        delta = current.investigation_coverage - previous.investigation_coverage
        direction = "rose" if delta > 0 else "fell"
        changes.append(
            f"Investigation coverage {direction} to {int(round(current.investigation_coverage * 100))}%."
        )
    return changes[:8]
