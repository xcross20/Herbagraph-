from agent_protocol.format import render_handoff
from agent_protocol.run_architect import plan_architect_action

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _pr():
    return {
        "number": 7,
        "body": render_handoff(task="HG-7", commit=SHA, pr_number=7),
        "labels": [{"name": "agent-loop"}],
        "head": {
            "ref": "grok/7-autonomous-review-loop",
            "sha": SHA,
            "repo": {"full_name": "xcross20/Herbagraph-", "fork": False},
        },
        "base": {"ref": "integration/agent", "repo": {"full_name": "xcross20/Herbagraph-"}},
    }


def test_plan_upserts_review_for_matching_sha():
    review = (
        '{"task":"HG-7","status":"CHANGES_REQUIRED",'
        f'"reviewed_commit":"{SHA}","blocking":["fix the gate"],'
        '"should_fix":[],"noted":[],"hostile_trace":"x","required_checks":[],'
        '"allowed_next_scope":"tests","next_owner":"GROK","trap_line":"no merge"}'
    )
    result = plan_architect_action(_pr(), [], review)
    assert result["qualified"] is True
    assert result["run_correction"] == "true"
    assert result["upsert_action"] == "create"
    assert SHA in result["comment_body"]


def test_plan_rejects_review_for_other_sha():
    review = (
        '{"task":"HG-7","status":"CHANGES_REQUIRED",'
        f'"reviewed_commit":"{OTHER}","blocking":["x"],'
        '"should_fix":[],"noted":[],"hostile_trace":"","required_checks":[],'
        '"allowed_next_scope":"","next_owner":"GROK","trap_line":""}'
    )
    result = plan_architect_action(_pr(), [], review)
    assert result["run_correction"] == "false"
    assert result["reason"] == "review_sha_mismatch"
