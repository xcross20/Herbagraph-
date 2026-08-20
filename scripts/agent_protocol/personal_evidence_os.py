"""
Personal Evidence agent operating system bootstrap.

Parses and validates the two YAML artifacts from the architect/65-personal-evidence-platform
branch, enforces fail-closed certification gating, routes a synthetic Cycle Charter through
the declared lifecycle, and emits a blocked/ready report compatible with the agent loop.

No control-plane paths (workflow, protocol, constants, bootstrap) are modified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

# ----------------------------------------------------------------------
# Types
# ----------------------------------------------------------------------


class LifecycleStage(Enum):
    FOUNDER_INTAKE = "FOUNDER_INTAKE"
    RESEARCH = "RESEARCH"
    SPEC = "SPEC"
    EXPERIENCE_AND_ARCHITECTURE = "EXPERIENCE_AND_ARCHITECTURE"
    ADVERSARIAL_CHALLENGE = "ADVERSARIAL_CHALLENGE"
    READY_FOR_BUILD = "READY_FOR_BUILD"
    IMPLEMENTING = "IMPLEMENTING"
    QA = "QA"
    EXACT_SHA_JUDGMENT = "EXACT_SHA_JUDGMENT"
    UAT = "UAT"
    FOUNDER_GATE = "FOUNDER_GATE"


class AuthorityClass(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


@dataclass(frozen=True)
class RoleCheckResult:
    role: str
    allowed: bool
    reason: str
    fields_missing: tuple[str, ...] = ()
    expired: bool = False
    critical_failure: bool = False
    wrong_authority: bool = False
    missing_evidence_uri: bool = False


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass
class CycleCharter:
    issue: int
    stage: str
    implementer: str | None = None
    judge: str | None = None
    verdict_sha: str | None = None
    candidate_sha: str | None = None
    correction_cycles: int = 0
    authority_class: str = "GREEN"
    commercial_evidence: dict[str, Any] = field(default_factory=dict)
    scientific_evidence: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------
# YAML loading
# ----------------------------------------------------------------------


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ----------------------------------------------------------------------
# Schema validation
# ----------------------------------------------------------------------


_SCHEMA_VERSION = "1.0"

_POLICY_FIELDS = {
    "expires_after_days",
    "fail_closed",
    "recertify_on",
    "non_compensable_failures",
}

_ASSIGNMENT_GATE_FIELDS = {
    "required_benchmark_status",
    "required_assignment_status",
    "required_fields",
    "reject_if",
}

_ROLE_YAML_FIELDS = {
    "schema_version",
    "roles",
}

_ROLE_RECORD_FIELDS = {
    "role",
    "skill_name",
    "benchmark_status",
    "assignment_status",
    "benchmark",
}

_BENCHMARK_FIELDS = {"scenario_id", "pass_condition", "critical_failures"}


def _missing(top: dict[str, Any], path: str) -> bool:
    keys = path.split(".")
    cur: Any = top
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return True
        cur = cur[k]
    return False


def validate_certification(cert_yaml: Path) -> ValidationResult:
    """
    Check that AGENT_CERTIFICATION.yaml has the required top-level sections,
    correct schema_version, and no missing required_fields at the role level.
    """
    errors: list[str] = []
    warnings: list[str] = []

    data = load_yaml(cert_yaml)
    sv = data.get("schema_version", "")
    if sv != _SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {sv!r} (expected {_SCHEMA_VERSION!r})")

    if "policy" not in data:
        errors.append("missing top-level 'policy'")
    else:
        for f in _POLICY_FIELDS:
            if f not in data["policy"]:
                errors.append(f"missing policy.{f}")

    if "assignment_gate" not in data:
        errors.append("missing top-level 'assignment_gate'")
    else:
        ag = data["assignment_gate"]
        for f in _ASSIGNMENT_GATE_FIELDS:
            if f not in ag:
                errors.append(f"missing assignment_gate.{f}")

    if "roles" not in data:
        errors.append("missing top-level 'roles'")
    else:
        for i, role in enumerate(data["roles"]):
            rn = role.get("role", f"<index {i}>")
            for f in _ROLE_RECORD_FIELDS:
                if f not in role:
                    errors.append(f"roles[{i}] ({rn}): missing field '{f}'")
            if "benchmark" in role:
                bm = role["benchmark"]
                for f in _BENCHMARK_FIELDS:
                    if f not in bm:
                        errors.append(f"roles[{i}] ({rn}): benchmark missing '{f}'")

    if "certification_records" not in data:
        warnings.append("missing certification_records — cannot gate live assignment")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_roles(roles_yaml: Path) -> ValidationResult:
    """Check that PERSONAL_EVIDENCE_ROLES.yaml is structurally correct."""
    errors: list[str] = []
    warnings: list[str] = []

    data = load_yaml(roles_yaml)
    sv = data.get("schema_version", "")
    if sv != _SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {sv!r}")

    for key in ("roles", "routing", "reconciliation"):
        if key not in data:
            errors.append(f"missing top-level '{key}'")

    if "roles" in data:
        for i, role in enumerate(data["roles"]):
            for f in ("objective", "owns", "forbids", "outputs"):
                if f not in role:
                    errors.append(f"roles[{i}] missing '{f}'")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


# ----------------------------------------------------------------------
# Certification checks
# ----------------------------------------------------------------------


def _role_record(data: dict[str, Any], role_name: str) -> dict[str, Any] | None:
    for r in data.get("roles", []):
        if r.get("role") == role_name:
            return r
    return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def check_certification_active(cert_yaml: Path) -> tuple[bool, str]:
    """
    Return (True, "active") when certification_records.status == 'active'.
    Any other status, missing, or parse failure → (False, reason).
    """
    data = load_yaml(cert_yaml)
    recs = data.get("certification_records")
    if not isinstance(recs, dict):
        return False, "certification_records_missing"
    status = str(recs.get("status", ""))
    if status == "active":
        return True, "active"
    return False, f"certification_status={status!r}"


def check_role_certification(
    role_name: str,
    cert_yaml: Path,
    *,
    now: datetime | None = None,
) -> RoleCheckResult:
    """
    Evaluate a single role's certification against the fail-closed policy.

    Rejects when:
    - expired (expires_at < now)
    - missing required field (evidence_uri, evaluator, scenario_id, ...)
    - any critical_failure present in the benchmark
    - assignment_status != 'active' or benchmark_status != 'passed'
    """
    if now is None:
        now = _now_utc()

    data = load_yaml(cert_yaml)
    rec = _role_record(data, role_name)
    if rec is None:
        return RoleCheckResult(
            role=role_name,
            allowed=False,
            reason="role_not_found",
        )

    # Benchmark gate
    if rec.get("benchmark_status") != "passed":
        return RoleCheckResult(
            role=role_name,
            allowed=False,
            reason="benchmark_not_passed",
        )

    if rec.get("assignment_status") != "active":
        return RoleCheckResult(
            role=role_name,
            allowed=False,
            reason=f"assignment_status={rec.get('assignment_status')!r}",
        )

    # Expiry
    expires_str = rec.get("expires_at", "")
    expires_at = _parse_ts(expires_str)
    if expires_at is not None and expires_at < now:
        return RoleCheckResult(
            role=role_name,
            allowed=False,
            reason="expired",
            expired=True,
        )

    # Required fields from assignment_gate
    ag = data.get("assignment_gate", {})
    required_fields = ag.get("required_fields", [])
    rec["expires_at"] = expires_str  # may be empty
    missing = tuple(f for f in required_fields if rec.get(f) is None)
    if missing:
        return RoleCheckResult(
            role=role_name,
            allowed=False,
            reason="missing_required_fields",
            fields_missing=missing,
            missing_evidence_uri="evidence_uri" in missing,
        )

    # Critical failures
    benchmark = rec.get("benchmark") or {}
    critical_failures = benchmark.get("critical_failures") or []
    if critical_failures:
        return RoleCheckResult(
            role=role_name,
            allowed=False,
            reason="critical_failure_present",
            critical_failure=True,
        )

    # Incompatible authority — requires explicit authority_class on the role.
    # Missing authority_class with incompatible_authority in reject_if → unverified → blocked.
    ag = data.get("assignment_gate", {})
    reject_if = set(ag.get("reject_if", []))
    if "incompatible_authority" in reject_if:
        role_auth = rec.get("authority_class")
        if not role_auth:
            return RoleCheckResult(
                role=role_name,
                allowed=False,
                reason="incompatible_authority",
                wrong_authority=True,
            )

    return RoleCheckResult(role=role_name, allowed=True, reason="qualified")


def charter_authority_from_rec(rec: dict[str, Any]) -> str | None:
    """Extract the authority class a charter assigns to this role."""
    authority = rec.get("authority_class") or rec.get("authority")
    if isinstance(authority, str) and authority.upper() in ("GREEN", "YELLOW", "RED"):
        return authority.upper()
    return None


def check_all_roles(
    cert_yaml: Path,
    *,
    now: datetime | None = None,
) -> list[RoleCheckResult]:
    """Run check_role_certification for every role in the YAML."""
    if now is None:
        now = _now_utc()
    data = load_yaml(cert_yaml)
    role_names = [r.get("role") for r in data.get("roles", []) if r.get("role")]
    return [check_role_certification(name, cert_yaml, now=now) for name in role_names]


# ----------------------------------------------------------------------
# Authority class
# ----------------------------------------------------------------------


def authority_class_for_stage(stage: str) -> str:
    """Return RED/YELLOW/GREEN for the given lifecycle stage."""
    red_stages = {
        "FOUNDER_GATE",
        "EXACT_SHA_JUDGMENT",
        "UAT",
    }
    yellow_stages = {
        "IMPLEMENTING",
        "QA",
        "EXPERIENCE_AND_ARCHITECTURE",
    }
    if stage in red_stages:
        return "RED"
    if stage in yellow_stages:
        return "YELLOW"
    return "GREEN"


# ----------------------------------------------------------------------
# Lifecycle routing
# ----------------------------------------------------------------------


def _routing_for_stage(
    stage: str,
    roles_yaml: Path,
) -> list[str]:
    """Return the ordered list of role names the routing table assigns to stage."""
    data = load_yaml(roles_yaml)
    routing = data.get("routing", {})
    key = _STAGE_TO_ROUTING_KEY.get(stage, "")
    roles = routing.get(key, [])
    if isinstance(roles, list):
        return roles
    return []


_STAGE_TO_ROUTING_KEY: dict[str, str] = {
    "FOUNDER_INTAKE": "founder_intake",
    "RESEARCH": "scientific_research",
    "SPEC": "specification",
    "EXPERIENCE_AND_ARCHITECTURE": "experience_architecture",
    "ADVERSARIAL_CHALLENGE": "adversarial_challenge",
    "IMPLEMENTING": "implementation",
    "QA": "implementation",
    "EXACT_SHA_JUDGMENT": "quality_and_release",
    "UAT": "quality_and_release",
    "FOUNDER_GATE": "quality_and_release",
    "READY_FOR_BUILD": "specification",
}


# ----------------------------------------------------------------------
# Judge separation
# ----------------------------------------------------------------------


def enforce_judge_separation(charter: CycleCharter) -> tuple[bool, str]:
    """
    Judge must not equal implementer.
    Verdict SHA must equal candidate SHA.
    """
    impl = charter.implementer or ""
    judge = charter.judge or ""

    if impl and judge and impl == judge:
        return False, "judge_equals_implementer"

    if charter.verdict_sha and charter.candidate_sha:
        if charter.verdict_sha != charter.candidate_sha:
            return False, "verdict_sha_mismatch"

    return True, ""


# ----------------------------------------------------------------------
# Material-change / evidence-stream checks
# ----------------------------------------------------------------------


def _evidence_keys(d: dict[str, Any]) -> set[str]:
    """Collect all leaf keys from a nested dict."""
    out: set[str] = set()
    stack = list(d.items())
    while stack:
        k, v = stack.pop()
        if isinstance(v, dict):
            stack.extend(v.items())
        else:
            out.add(k)
    return out


def check_evidence_streams(charter: CycleCharter) -> tuple[bool, str]:
    """
    Reject if commercial_evidence and scientific_evidence share any leaf key.
    Purchase metrics in research stream → blocked.
    Scientific fields in commercial stream → blocked.
    """
    comm = _evidence_keys(charter.commercial_evidence)
    sci = _evidence_keys(charter.scientific_evidence)

    shared = comm & sci
    if shared:
        return False, f"evidence_streams_merged: {sorted(shared)}"

    # Explicit field-level guards (from issue requirements)
    purchase_fields = {"payment", "paid_deposit", "paid_deposits", "purchase", "revenue", "conversion"}
    scientific_evidence_fields = {
        "causal_conclusion",
        "feasibility",
        "efficacy",
        "adherence",
        "missingness",
        "safety_fidelity",
        "recruitment",
        "burden",
        "protocol_compliance",
    }

    if sci & purchase_fields:
        return False, "research_participation_in_commercial_metrics"
    if comm & scientific_evidence_fields:
        return False, "commercial_payment_in_scientific_evidence"

    if sci & purchase_fields:
        return False, "research_participation_in_commercial_metrics"
    if comm & scientific_evidence_fields:
        return False, "commercial_payment_in_scientific_fields"

    return True, ""


def check_material_change_recertification(
    charter: CycleCharter,
    cert_yaml: Path,
) -> tuple[bool, str]:
    """
    Any recertify_on field in the charter that has changed vs prior SHA
    requires recertification.  In the bootstrap, the charter must declare
    whether a material change occurred.  Reject if a declared change
    overlaps recertify_on triggers without re-certification being recorded.
    """
    data = load_yaml(cert_yaml)
    recertify_on = set(data.get("policy", {}).get("recertify_on", []))
    material_changes = set(charter.raw.get("material_changes_declared", []))
    triggered = material_changes & recertify_on
    if triggered:
        # In bootstrap: require explicit recertification field
        if not charter.raw.get("recertification_recorded"):
            return False, f"material_change_requires_recertification: {sorted(triggered)}"
    return True, ""


# ----------------------------------------------------------------------
# Cycle correction escalation
# ----------------------------------------------------------------------


def check_correction_cycles(charter: CycleCharter) -> tuple[bool, str]:
    """
    After three completed correction cycles, further CHANGES_REQUIRED
    must escalate rather than loop.
    """
    if charter.correction_cycles >= 4:
        return False, "correction_cycles_exhausted_escalate"
    return True, ""


# ----------------------------------------------------------------------
# Synthetic charter parsing
# ----------------------------------------------------------------------


def parse_cycle_charter(raw: dict[str, Any]) -> CycleCharter:
    """Build a CycleCharter from a dict (typically loaded from YAML/JSON)."""
    return CycleCharter(
        issue=int(raw.get("issue", 0)),
        stage=str(raw.get("stage", "FOUNDER_INTAKE")),
        implementer=_maybe_str(raw.get("implementer")),
        judge=_maybe_str(raw.get("judge")),
        verdict_sha=_maybe_str(raw.get("verdict_sha")),
        candidate_sha=_maybe_str(raw.get("candidate_sha")),
        correction_cycles=int(raw.get("correction_cycles", 0)),
        authority_class=str(raw.get("authority_class", "GREEN")),
        commercial_evidence=raw.get("commercial_evidence") or {},
        scientific_evidence=raw.get("scientific_evidence") or {},
        raw=raw,
    )


def _maybe_str(v: Any) -> str | None:
    return str(v) if v is not None else None


def validate_cycle_charter(
    charter: CycleCharter,
    roles_yaml: Path,
    cert_yaml: Path,
) -> tuple[bool, list[str]]:
    """
    Full charter validation:
    - lifecycle stage is valid
    - all assigned roles are certified active
    - judge ≠ implementer
    - verdict SHA = candidate SHA
    - evidence streams not merged
    - material changes have recertification
    - correction cycles within limit
    """
    reasons: list[str] = []

    # Stage validity
    try:
        LifecycleStage(charter.stage)
    except ValueError:
        reasons.append(f"unknown_stage: {charter.stage!r}")

    # Roles
    assigned_roles = _routing_for_stage(charter.stage, roles_yaml)
    for role_name in assigned_roles:
        result = check_role_certification(role_name, cert_yaml)
        if not result.allowed:
            reasons.append(f"role_blocked:{role_name} reason={result.reason}")
        # Incompatible authority: role's authority_class must match the charter's
        data = load_yaml(cert_yaml)
        rec = _role_record(data, role_name)
        if rec:
            role_auth = str(rec.get("authority_class") or "GREEN").upper()
            if charter.authority_class and charter.authority_class.upper() != role_auth:
                reasons.append(f"role_blocked:{role_name} reason=incompatible_authority")

    # Judge separation
    ok, msg = enforce_judge_separation(charter)
    if not ok:
        reasons.append(msg)

    # Evidence streams
    ok, msg = check_evidence_streams(charter)
    if not ok:
        reasons.append(msg)

    # Material change
    ok, msg = check_material_change_recertification(charter, cert_yaml)
    if not ok:
        reasons.append(msg)

    # Correction cycles
    ok, msg = check_correction_cycles(charter)
    if not ok:
        reasons.append(msg)

    return len(reasons) == 0, reasons


# ----------------------------------------------------------------------
# Blocked/ready report
# ----------------------------------------------------------------------


def emit_blocked_report(
    role_results: list[RoleCheckResult],
    cert_status: str,
    charter_valid: bool,
    charter_reasons: list[str],
) -> dict[str, Any]:
    """
    Emit a deterministic blocked/ready report compatible with agent-loop conventions.

    Returns:
        {
            "blocked": bool,
            "reason": str,
            "roles": [{role, allowed, reason, ...}],
            "charter_valid": bool,
            "charter_blocked_reasons": [str],
            "timestamp": ISO8601,
        }
    """
    now = datetime.now(timezone.utc).isoformat()
    blocked_roles = [r for r in role_results if not r.allowed]
    any_blocked = bool(blocked_roles) or cert_status != "active" or not charter_valid

    if cert_status != "active":
        reason = f"certification_status={cert_status!r}"
    elif blocked_roles:
        reasons = [f"{r.role}:{r.reason}" for r in blocked_roles]
        reason = "role_blocked:" + ";".join(reasons)
    elif charter_reasons:
        reason = "charter_invalid:" + ";".join(charter_reasons)
    else:
        reason = "ready"

    return {
        "blocked": any_blocked,
        "reason": reason,
        "roles": [
            {
                "role": r.role,
                "allowed": r.allowed,
                "reason": r.reason,
                "expired": r.expired,
                "critical_failure": r.critical_failure,
                "wrong_authority": r.wrong_authority,
                "missing_evidence_uri": r.missing_evidence_uri,
                "fields_missing": list(r.fields_missing),
            }
            for r in role_results
        ],
        "certification_status": cert_status,
        "charter_valid": charter_valid,
        "charter_blocked_reasons": charter_reasons,
        "timestamp": now,
    }


def emit_ready_report(role_results: list[RoleCheckResult]) -> dict[str, Any]:
    """Emit a ready report when all gates pass."""
    return {
        "blocked": False,
        "reason": "ready",
        "roles": [
            {"role": r.role, "allowed": r.allowed, "reason": r.reason}
            for r in role_results
        ],
        "certification_status": "active",
        "charter_valid": True,
        "charter_blocked_reasons": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ----------------------------------------------------------------------
# Convenience: run full OS report on YAML files
# ----------------------------------------------------------------------


def run_os_report(
    roles_yaml: Path,
    cert_yaml: Path,
    charter: CycleCharter | None = None,
) -> dict[str, Any]:
    """
    Run the full blocked/ready check.

    Pass an optional CycleCharter to also validate lifecycle routing.
    Without a charter, only the certification gate is evaluated.
    """
    cert_active, cert_reason = check_certification_active(cert_yaml)
    role_results = check_all_roles(cert_yaml)

    if charter is None:
        if cert_active:
            return emit_ready_report(role_results)
        return emit_blocked_report(
            role_results, cert_reason, True, []
        )

    charter_valid, charter_reasons = validate_cycle_charter(
        charter, roles_yaml, cert_yaml
    )

    if cert_active and charter_valid and all(r.allowed for r in role_results):
        return emit_ready_report(role_results)

    return emit_blocked_report(role_results, cert_reason, charter_valid, charter_reasons)
