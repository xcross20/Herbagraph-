from agent_protocol.parse import ArchitectReview
from agent_protocol.qualify import PullRequestView, qualify_pull_request
from agent_protocol.stop import action_is_forbidden, decide_after_review

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _pr(**overrides) -> PullRequestView:
    data = dict(
        number=7,
        base_ref="integration/agent",
        head_ref="grok/7-autonomous-review-loop",
        head_sha=SHA,
        head_repo="xcross20/Herbagraph-",
        base_repo="xcross20/Herbagraph-",
        labels=frozenset({"agent-loop"}),
        is_fork=False,
    )
    data.update(overrides)
    return PullRequestView(**data)


def test_fork_and_non_grok_heads_are_rejected():
    fork = _pr(is_fork=True, head_repo="outsider/Herbagraph-")
    assert qualify_pull_request(fork, handoff_sha=SHA).allowed is False
    other = _pr(head_ref="feature/loop")
    assert qualify_pull_request(other, handoff_sha=SHA).reason == "head_must_be_grok_branch"
    excluded = _pr(head_ref="grok/mvp-baseline-red-tests")
    assert qualify_pull_request(excluded, handoff_sha=SHA).reason == "head_explicitly_excluded_from_rollout"


def test_approval_never_merges():
    review = ArchitectReview(task="HG-7", reviewed_commit=SHA, status="ARCHITECT_APPROVED")
    decision = decide_after_review(review, head_sha=SHA, completed_cycles=0)
    assert decision.run_correction is False
    assert decision.continue_automation is False
    assert decision.reason == "architect_approved_no_merge"
    assert action_is_forbidden("merge") is True
    assert action_is_forbidden("deploy") is True


def test_three_cycles_then_founder_decision():
    review = ArchitectReview(task="HG-7", reviewed_commit=SHA, status="CHANGES_REQUIRED")
    decision = decide_after_review(review, head_sha=SHA, completed_cycles=3)
    assert decision.run_correction is False
    assert decision.label == "founder-decision-required"
    assert decision.reason == "correction_cycle_limit"


def test_stale_review_does_not_correct_newer_head():
    review = ArchitectReview(task="HG-7", reviewed_commit=SHA, status="CHANGES_REQUIRED")
    decision = decide_after_review(review, head_sha=OTHER, completed_cycles=0)
    assert decision.run_correction is False
    assert decision.reason == "stale_review_sha"
