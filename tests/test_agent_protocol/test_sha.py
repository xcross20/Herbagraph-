from agent_protocol.parse import extract_full_sha, parse_handoff
from agent_protocol.qualify import PullRequestView, qualify_pull_request
from agent_protocol.stop import review_matches_head
from agent_protocol.parse import ArchitectReview

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_extract_full_sha_ignores_short_hashes():
    assert extract_full_sha("Commit: abcdef1") is None
    assert extract_full_sha(f"Commit: {SHA}") == SHA


def test_handoff_must_match_current_head():
    pr = PullRequestView(
        number=1,
        base_ref="integration/agent",
        head_ref="grok/7-autonomous-review-loop",
        head_sha=SHA,
        head_repo="xcross20/Herbagraph-",
        base_repo="xcross20/Herbagraph-",
        labels=frozenset({"agent-loop"}),
        is_fork=False,
    )
    assert qualify_pull_request(pr, handoff_sha=SHA).allowed is True
    assert qualify_pull_request(pr, handoff_sha=OTHER).allowed is False
    assert qualify_pull_request(pr, handoff_sha=None).reason == "handoff_must_identify_head_sha"


def test_stale_review_cannot_target_newer_sha():
    review = ArchitectReview(task="HG-7", reviewed_commit=SHA, status="CHANGES_REQUIRED")
    assert review_matches_head(review, SHA) is True
    assert review_matches_head(review, OTHER) is False


def test_parse_handoff_from_pr_body():
    body = f"HERBAGRAPH_IMPLEMENTATION_REPORT\nTask: HG-7\nStatus: READY_FOR_ARCHITECT\nCommit: {SHA}\n"
    parsed = parse_handoff(body)
    assert parsed is not None
    assert parsed.commit == SHA
