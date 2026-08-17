from agent_protocol.parse import parse_review_json, parse_verdict


def test_parse_verdict_accepts_known_statuses():
    assert parse_verdict("Status: CHANGES_REQUIRED") == "CHANGES_REQUIRED"
    assert parse_verdict("Status: ARCHITECT_APPROVED") == "ARCHITECT_APPROVED"
    assert parse_verdict("Status: FOUNDER_DECISION_REQUIRED") == "FOUNDER_DECISION_REQUIRED"


def test_parse_verdict_rejects_unknown_status():
    assert parse_verdict("Status: LGTM") is None
    assert parse_verdict("") is None


def test_parse_review_json_requires_full_sha_and_verdict():
    parsed = parse_review_json(
        '{"status":"CHANGES_REQUIRED","reviewed_commit":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","blocking":["fix"]}'
    )
    assert parsed is not None
    assert parsed.status == "CHANGES_REQUIRED"
    assert parsed.blocking == ("fix",)
    assert parse_review_json('{"status":"CHANGES_REQUIRED","reviewed_commit":"abc"}') is None
