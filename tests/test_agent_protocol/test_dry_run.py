from agent_protocol.dry_run import run_dry_run


def test_dry_run_completes_changes_required_correction_and_rereview():
    result = run_dry_run()
    assert result["first_verdict"] == "CHANGES_REQUIRED"
    assert result["duplicate_action"] == "noop"
    assert result["stale_reason"] == "stale_review_sha"
    assert result["second_reason"] == "architect_approved_uat_ready"
    assert result["merged"] is False
    assert result["deployed"] is False
