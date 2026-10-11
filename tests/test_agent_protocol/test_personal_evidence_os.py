"""Red-first tests for the Personal Evidence OS bootstrap (issue #67)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from scripts.agent_protocol.personal_evidence_os import (
    CycleCharter,
    check_certification_active,
    check_material_change_recertification,
    check_role_certification,
    check_all_roles,
    check_evidence_streams,
    check_correction_cycles,
    enforce_judge_separation,
    emit_blocked_report,
    emit_ready_report,
    parse_cycle_charter,
    run_os_report,
    validate_certification,
    validate_cycle_charter,
    validate_roles,
)

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures" / "personal_evidence_os.yaml"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return yaml.safe_load(data[name])


def _dump_str(value: dict | str) -> str:
    if isinstance(value, str):
        return value
    return yaml.safe_dump(value, default_flow_style=False)


# ----------------------------------------------------------------------
# Certification schema validation
# ----------------------------------------------------------------------


class TestValidateCertification:
    def test_valid_cert_file(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        result = validate_certification(cert)
        assert result.valid, result.errors

    def test_missing_policy(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text("schema_version: '1.0'\nroles: []\n", encoding="utf-8")
        result = validate_certification(cert)
        assert not result.valid
        assert any("policy" in e for e in result.errors)

    def test_missing_assignment_gate(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text("schema_version: '1.0'\npolicy: {}\nroles: []\n", encoding="utf-8")
        result = validate_certification(cert)
        assert not result.valid
        assert any("assignment_gate" in e for e in result.errors)

    def test_wrong_schema_version(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(
            "schema_version: '99.0'\npolicy: {}\nassignment_gate: {}\nroles: []\n",
            encoding="utf-8",
        )
        result = validate_certification(cert)
        assert not result.valid
        assert any("schema_version" in e for e in result.errors)


# ----------------------------------------------------------------------
# Active certification gate
# ----------------------------------------------------------------------


class TestCertificationActive:
    def test_active_status(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        ok, reason = check_certification_active(cert)
        assert ok
        assert reason == "active"

    def test_evidence_pending_blocked(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_blocked_pending")), encoding="utf-8")
        ok, reason = check_certification_active(cert)
        assert not ok
        assert "evidence_pending" in reason

    def test_missing_certification_records(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text("schema_version: '1.0'\nroles: []\n", encoding="utf-8")
        ok, reason = check_certification_active(cert)
        assert not ok
        assert "missing" in reason


# ----------------------------------------------------------------------
# Role certification checks
# ----------------------------------------------------------------------


class TestRoleCertification:
    def test_expired_role_rejected(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("role_expired")), encoding="utf-8")
        result = check_role_certification(
            "expired_test_role", cert, now=datetime(2026, 8, 1, tzinfo=timezone.utc)
        )
        assert not result.allowed
        assert result.reason == "expired"
        assert result.expired

    def test_missing_evidence_uri_rejected(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("role_missing_evidence_uri")), encoding="utf-8")
        result = check_role_certification("missing_uri_role", cert)
        assert not result.allowed
        assert result.missing_evidence_uri
        assert "evidence_uri" in result.fields_missing

    def test_critical_failure_rejects_role(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("role_critical_failure")), encoding="utf-8")
        result = check_role_certification("critical_fail_role", cert)
        assert not result.allowed
        assert result.critical_failure
        assert result.reason == "critical_failure_present"

    def test_wrong_authority_rejected(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("role_wrong_authority")), encoding="utf-8")
        result = check_role_certification("wrong_authority_role", cert)
        assert not result.allowed
        assert result.wrong_authority

    def test_benchmark_not_passed_rejected(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(
            "schema_version: '1.0'\n"
            "policy: {expires_after_days: 90, fail_closed: true, recertify_on: [], non_compensable_failures: []}\n"
            "assignment_gate: {required_benchmark_status: passed, required_assignment_status: active, "
            "required_fields: [role], reject_if: [expired]}\n"
            "roles:\n"
            "  - role: test_role\n"
            "    benchmark_status: failed\n"
            "    assignment_status: active\n"
            "    benchmark: {scenario_id: s1, pass_condition: ok, critical_failures: []}\n"
            "certification_records: {status: active}",
            encoding="utf-8",
        )
        result = check_role_certification("test_role", cert)
        assert not result.allowed
        assert "not_passed" in result.reason

    def test_assignment_not_active_rejected(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(
            "schema_version: '1.0'\n"
            "policy: {expires_after_days: 90, fail_closed: true, recertify_on: [], non_compensable_failures: []}\n"
            "assignment_gate: {required_benchmark_status: passed, required_assignment_status: active, "
            "required_fields: [role], reject_if: [expired]}\n"
            "roles:\n"
            "  - role: test_role\n"
            "    benchmark_status: passed\n"
            "    assignment_status: inactive\n"
            "    benchmark: {scenario_id: s1, pass_condition: ok, critical_failures: []}\n"
            "certification_records: {status: active}",
            encoding="utf-8",
        )
        result = check_role_certification("test_role", cert)
        assert not result.allowed
        assert "inactive" in result.reason

    def test_role_not_found(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        result = check_role_certification("nonexistent_role", cert)
        assert not result.allowed
        assert result.reason == "role_not_found"

    def test_check_all_roles_filters_blocked(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        results = check_all_roles(cert)
        assert all(r.role in ("mission_control", "demand_intelligence") for r in results)
        assert all(r.allowed for r in results)


# ----------------------------------------------------------------------
# Judge separation
# ----------------------------------------------------------------------


class TestJudgeSeparation:
    def test_judge_equals_implementer_blocked(self) -> None:
        charter = parse_cycle_charter(_load_fixture("cycle_judge_equals_implementer"))
        ok, reason = enforce_judge_separation(charter)
        assert not ok
        assert reason == "judge_equals_implementer"

    def test_verdict_sha_mismatch_blocked(self) -> None:
        charter = parse_cycle_charter(_load_fixture("cycle_wrong_sha"))
        ok, reason = enforce_judge_separation(charter)
        assert not ok
        assert reason == "verdict_sha_mismatch"

    def test_valid_sha_separation_passes(self) -> None:
        charter = parse_cycle_charter(_load_fixture("synthetic_charter_valid"))
        ok, reason = enforce_judge_separation(charter)
        assert ok
        assert reason == ""

    def test_missing_shas_passes_without_judgment(self) -> None:
        charter = CycleCharter(issue=67, stage="FOUNDER_INTAKE")
        ok, reason = enforce_judge_separation(charter)
        assert ok


# ----------------------------------------------------------------------
# Evidence stream separation
# ----------------------------------------------------------------------


class TestEvidenceStreams:
    def test_commercial_and_scientific_merged_rejected(self) -> None:
        charter = parse_cycle_charter(_load_fixture("cycle_commercial_in_research"))
        ok, reason = check_evidence_streams(charter)
        # paid_deposits (purchase metric) appears in commercial AND feasibility/efficacy in scientific
        assert not ok

    def test_research_participation_in_commercial_metrics_rejected(self) -> None:
        charter = parse_cycle_charter(_load_fixture("cycle_payment_in_scientific"))
        ok, reason = check_evidence_streams(charter)
        # paid_deposits in commercial; feasibility/efficacy in scientific
        assert not ok

    def test_payment_in_scientific_fields_rejected(self) -> None:
        charter = parse_cycle_charter(_load_fixture("cycle_payment_in_scientific"))
        ok, reason = check_evidence_streams(charter)
        assert not ok

    def test_separate_streams_pass(self) -> None:
        charter = CycleCharter(
            issue=67,
            stage="RESEARCH",
            commercial_evidence={"paid_deposits": 3},
            scientific_evidence={"adherence": 0.85},
        )
        ok, reason = check_evidence_streams(charter)
        assert ok


# ----------------------------------------------------------------------
# Material-change recertification
# ----------------------------------------------------------------------


class TestMaterialChange:
    def test_material_change_without_recertification_rejected(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        charter = parse_cycle_charter(_load_fixture("cycle_changed_material"))
        ok, reason = check_material_change_recertification(charter, cert)
        assert not ok
        assert "recertification" in reason

    def test_material_change_with_recertification_passes(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        raw = _load_fixture("cycle_changed_material")
        raw["recertification_recorded"] = True
        charter = parse_cycle_charter(raw)
        ok, reason = check_material_change_recertification(charter, cert)
        assert ok


# ----------------------------------------------------------------------
# Correction cycle escalation
# ----------------------------------------------------------------------


class TestCorrectionCycles:
    def test_three_cycles_allowed(self) -> None:
        charter = CycleCharter(issue=67, stage="QA", correction_cycles=3)
        ok, reason = check_correction_cycles(charter)
        assert ok

    def test_four_cycles_escalates_not_loops(self) -> None:
        charter = parse_cycle_charter(_load_fixture("correction_cycles_exhausted"))
        ok, reason = check_correction_cycles(charter)
        assert not ok
        assert "escalate" in reason


# ----------------------------------------------------------------------
# Full charter validation
# ----------------------------------------------------------------------


class TestValidateCycleCharter:
    def test_valid_charter_passes(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        roles = tmp_path / "roles.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        roles.write_text(_dump_str(_load_fixture("roles_valid")), encoding="utf-8")
        charter = parse_cycle_charter(_load_fixture("synthetic_charter_valid"))
        charter = CycleCharter(
            issue=67,
            stage="FOUNDER_INTAKE",
            implementer="agent_x",
            judge="agent_y",
            verdict_sha="abcdef0123456789abcdef0123456789abcdef01",
            candidate_sha="abcdef0123456789abcdef0123456789abcdef01",
            correction_cycles=0,
            authority_class="GREEN",
            commercial_evidence={"paid_deposits": 0},
            scientific_evidence={"adherence": 0.0},
        )
        ok, reasons = validate_cycle_charter(charter, roles, cert)
        assert ok, reasons

    def test_invalid_stage_rejected(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        roles = tmp_path / "roles.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        roles.write_text(_dump_str(_load_fixture("roles_valid")), encoding="utf-8")
        charter = CycleCharter(issue=67, stage="NOT_A_STAGE")
        ok, reasons = validate_cycle_charter(charter, roles, cert)
        assert not ok
        assert any("stage" in r for r in reasons)


# ----------------------------------------------------------------------
# Blocked/ready report
# ----------------------------------------------------------------------


class TestBlockedReport:
    def test_inactive_certification_produces_blocked(self) -> None:
        report = emit_blocked_report([], "evidence_pending_repository_registration", True, [])
        assert report["blocked"]
        assert "evidence_pending" in report["reason"]

    def test_role_blocked_in_report(self) -> None:
        from scripts.agent_protocol.personal_evidence_os import RoleCheckResult

        results = [
            RoleCheckResult(
                role="test_role",
                allowed=False,
                reason="expired",
                expired=True,
            )
        ]
        report = emit_blocked_report(results, "active", True, [])
        assert report["blocked"]
        assert "test_role" in report["reason"]
        assert report["roles"][0]["expired"]

    def test_ready_report_when_all_pass(self) -> None:
        from scripts.agent_protocol.personal_evidence_os import RoleCheckResult

        results = [
            RoleCheckResult(role="role_a", allowed=True, reason="qualified")
        ]
        report = emit_ready_report(results)
        assert not report["blocked"]
        assert report["reason"] == "ready"

    def test_report_fields_present(self) -> None:
        from scripts.agent_protocol.personal_evidence_os import RoleCheckResult

        results = [RoleCheckResult(role="r", allowed=True, reason="qualified")]
        report = emit_ready_report(results)
        for key in ("blocked", "reason", "roles", "certification_status", "timestamp"):
            assert key in report


# ----------------------------------------------------------------------
# Run full OS report
# ----------------------------------------------------------------------


class TestRunOsReport:
    def test_report_blocked_when_cert_not_active(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        roles = tmp_path / "roles.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_blocked_pending")), encoding="utf-8")
        roles.write_text(_dump_str(_load_fixture("roles_valid")), encoding="utf-8")
        report = run_os_report(roles, cert)
        assert report["blocked"]
        assert "evidence_pending" in report["reason"]

    def test_report_blocked_when_role_expired(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        roles = tmp_path / "roles.yaml"
        cert.write_text(_dump_str(_load_fixture("role_expired")), encoding="utf-8")
        roles.write_text(_dump_str(_load_fixture("roles_valid")), encoding="utf-8")
        report = run_os_report(
            roles,
            cert,
            charter=parse_cycle_charter(_load_fixture("synthetic_charter_valid")),
        )
        assert report["blocked"]

    def test_report_ready_when_all_gates_pass(self, tmp_path: Path) -> None:
        cert = tmp_path / "cert.yaml"
        roles = tmp_path / "roles.yaml"
        cert.write_text(_dump_str(_load_fixture("cert_active_valid")), encoding="utf-8")
        roles.write_text(_dump_str(_load_fixture("roles_valid")), encoding="utf-8")
        charter = CycleCharter(
            issue=67,
            stage="FOUNDER_INTAKE",
            implementer="agent_x",
            judge="agent_y",
            verdict_sha="abcdef0123456789abcdef0123456789abcdef01",
            candidate_sha="abcdef0123456789abcdef0123456789abcdef01",
            correction_cycles=0,
            authority_class="GREEN",
            commercial_evidence={"paid_deposits": 0},
            scientific_evidence={"adherence": 0.0},
        )
        report = run_os_report(roles, cert, charter=charter)
        assert not report["blocked"]
        assert report["reason"] == "ready"
