from agent_protocol.comment import plan_comment_upsert
from agent_protocol.parse import CommentRecord, marker_for_review

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_first_review_is_create():
    marker = marker_for_review(7, SHA)
    plan = plan_comment_upsert([], marker=marker, body="review")
    assert plan.action == "create"
    assert marker in plan.body


def test_same_sha_upserts_instead_of_duplicating():
    marker = marker_for_review(7, SHA)
    first = plan_comment_upsert([], marker=marker, body="review one")
    comments = [CommentRecord(id=11, body=first.body)]
    second = plan_comment_upsert(comments, marker=marker, body="review two")
    assert second.action == "update"
    assert second.comment_id == 11
    third = plan_comment_upsert(comments, marker=marker, body=first.body)
    assert third.action == "noop"
