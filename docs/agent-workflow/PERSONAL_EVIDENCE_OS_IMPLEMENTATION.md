# Personal Evidence Agent OS — Implementation Report

**Issue:** #67  
**Branch:** `grok/67-personal-evidence-agent-os-bootstrap`  
**SHA:** `$(git rev-parse HEAD)`  
**Status:** `READY_FOR_ARCHITECT`

---

## What was implemented

A minimal automation/control-plane slice that parses and validates the two YAML
artifacts from the architect/65-personal-evidence-platform branch and enforces
fail-closed certification gating for the Personal Evidence agent operating system.

### New file: `scripts/agent_protocol/personal_evidence_os.py`

| Function | Purpose |
|---|---|
| `validate_certification(Path)` | Schema check: required top-level sections, `schema_version`, role record completeness |
| `validate_roles(Path)` | Schema check for `PERSONAL_EVIDENCE_ROLES.yaml` |
| `check_certification_active(Path)` | Returns `(True, "active")` or `(False, reason)`. Fails closed on any non-`active` status |
| `check_role_certification(str, Path, *, now?)` | Per-role gate: benchmark passed, assignment active, not expired, all required fields present, no critical failures, `authority_class` set when `incompatible_authority` is in `reject_if` |
| `check_all_roles(Path)` | Runs `check_role_certification` for every role in the YAML |
| `enforce_judge_separation(CycleCharter)` | Judge ≠ implementer; verdict SHA = candidate SHA |
| `check_evidence_streams(CycleCharter)` | Blocks shared leaf keys between `commercial_evidence` and `scientific_evidence`; blocks purchase fields in scientific; blocks scientific fields in commercial |
| `check_material_change_recertification(CycleCharter, Path)` | Declared `material_changes_declared` overlapping `recertify_on` triggers requires `recertification_recorded=True` |
| `check_correction_cycles(CycleCharter)` | 4th correction cycle → escalation, not loop |
| `validate_cycle_charter(Charter, roles_yaml, cert_yaml)` | Full charter gate: valid stage, all assigned roles certified, judge separation, evidence streams, material change, cycle limit |
| `parse_cycle_charter(dict)` | Builds a `CycleCharter` from YAML/JSON dict |
| `emit_blocked_report(...)` / `emit_ready_report(...)` | Agent-loop-compatible JSON report |
| `run_os_report(roles_yaml, cert_yaml, charter?)` | Full gate: cert → roles → charter; returns blocked/ready report |

### New tests: `tests/test_agent_protocol/test_personal_evidence_os.py`

36 tests, all passing. Fixtures in `tests/test_agent_protocol/fixtures/personal_evidence_os.yaml`.

| Test | What it checks |
|---|---|
| `test_valid_cert_file` | Schema-valid cert passes |
| `test_missing_policy` | Missing `policy` → rejected |
| `test_missing_assignment_gate` | Missing `assignment_gate` → rejected |
| `test_wrong_schema_version` | Wrong `schema_version` → rejected |
| `test_active_status` | `status=active` → ready |
| `test_evidence_pending_blocked` | `status=evidence_pending_repository_registration` → blocked |
| `test_missing_certification_records` | Missing registry → blocked |
| `test_expired_role_rejected` | `expires_at` in the past → blocked |
| `test_missing_evidence_uri_rejected` | Missing `evidence_uri` → blocked |
| `test_critical_failure_rejects_role` | Any `critical_failure` → blocked regardless of score |
| `test_wrong_authority_rejected` | `incompatible_authority` in `reject_if` + no `authority_class` → blocked |
| `test_benchmark_not_passed_rejected` | `benchmark_status != passed` → blocked |
| `test_assignment_not_active_rejected` | `assignment_status != active` → blocked |
| `test_role_not_found` | Unknown role → blocked |
| `test_check_all_roles_filters_blocked` | All roles in valid cert are allowed |
| `test_judge_equals_implementer_blocked` | Same agent in both roles → blocked |
| `test_verdict_sha_mismatch_blocked` | `verdict_sha != candidate_sha` → blocked |
| `test_valid_sha_separation_passes` | Different agents + matching SHA → allowed |
| `test_missing_shas_passes_without_judgment` | No SHA set in early stage → passes |
| `test_commercial_and_scientific_merged_rejected` | Shared leaf keys → blocked |
| `test_research_participation_in_commercial_metrics_rejected` | `revenue` in `scientific_evidence` → blocked |
| `test_payment_in_scientific_fields_rejected` | `feasibility` in `commercial_evidence` → blocked |
| `test_separate_streams_pass` | Cleanly separated streams → passes |
| `test_material_change_without_recertification_rejected` | Declared change + no recertification → blocked |
| `test_material_change_with_recertification_passes` | Declared change + `recertification_recorded=True` → passes |
| `test_three_cycles_allowed` | 3 correction cycles → allowed |
| `test_four_cycles_escalates_not_loops` | 4th cycle → blocked with escalation reason |
| `test_valid_charter_passes` | Valid cert + valid charter → passes |
| `test_invalid_stage_rejected` | Unknown stage name → rejected |
| `test_inactive_certification_produces_blocked` | Non-active status → blocked report |
| `test_role_blocked_in_report` | Blocked role appears in report `roles` list |
| `test_ready_report_when_all_pass` | All clear → unblocked ready report |
| `test_report_fields_present` | Report has all required keys |
| `test_report_blocked_when_cert_not_active` | Full gate: cert not active → blocked |
| `test_report_blocked_when_role_expired` | Full gate: role expired → blocked |
| `test_report_ready_when_all_gates_pass` | Full gate: all pass → ready |

### New documentation: `docs/agent-workflow/PERSONAL_EVIDENCE_OS_IMPLEMENTATION.md`

This file.

---

## Files changed

```
scripts/agent_protocol/personal_evidence_os.py      [NEW]
tests/test_agent_protocol/test_personal_evidence_os.py  [NEW]
tests/test_agent_protocol/fixtures/personal_evidence_os.yaml  [NEW]
docs/agent-workflow/PERSONAL_EVIDENCE_OS_IMPLEMENTATION.md  [NEW]
docs/agent-workflow/AGENT_CERTIFICATION.yaml       [NEW — from architect branch]
docs/agent-workflow/PERSONAL_EVIDENCE_AGENT_OS.md [NEW — from architect branch]
docs/agent-workflow/PERSONAL_EVIDENCE_ROLES.yaml  [NEW — from architect branch]
```

No existing files were modified.

---

## Commands

```bash
# Unit tests
python3 -m pytest tests/test_agent_protocol/test_personal_evidence_os.py -v

# Full protocol suite
python3 -m pytest tests/test_agent_protocol/ -q

# Dry run
python3 scripts/agent_protocol/dry_run.py
```

---

## Rollback

```bash
git checkout integration/agent -- .
git branch -D grok/67-personal-evidence-agent-os-bootstrap
```

No migrations, no data model changes, no production impact.

---

## SHA baseline

```
Architect branch:     38cd52460f19711fac4be7b338ae619f80ddd8b9  (PR #66 PASS)
Integration/agent:    1a9fcd0
Workflow (from main):  herbagraph-agent-loop.yml current SHA  (protected, not modified)
```

---

## Limitations

- No actual LLM/agent invocation — purely structural validation of YAML artifacts
- No live GitHub API calls from this module
- `authority_class` mismatch check requires `authority_class` to be explicitly set on the role record; implicit authority is treated as `GREEN`
- The module does not write to GitHub — it is a library consumed by the workflow or a UAT harness
- Certification records are not updated by this code; that is a Founder/Mission Control action

---

## Open items (not in scope for this PR)

- Integration with the GitHub Actions workflow (optional job in `herbagraph-agent-loop.yml`)
- Updating `certification_records.status` from `evidence_pending_repository_registration`
- Live agent invocation with role assignment
- PHI-safe artifact routing
