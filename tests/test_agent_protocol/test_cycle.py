from agent_protocol.constants import MAX_CORRECTION_CYCLES
from agent_protocol.cycle import completed_correction_cycles, cycles_exhausted, next_cycle_number
from agent_protocol.format import render_architect_review, render_correction_report
from agent_protocol.parse import ArchitectReview, CommentRecord

SHA1 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SHA2 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
SHA3 = "cccccccccccccccccccccccccccccccccccccccc"


def _review(sha: str) -> CommentRecord:
    body = render_architect_review(
        ArchitectReview(task="HG-7", reviewed_commit=sha, status="CHANGES_REQUIRED", blocking=("x",)),
        pr_number=7,
    )
    return CommentRecord(id=None, body=body)


def _correction(reviewed: str, new: str, cycle: int) -> CommentRecord:
    return CommentRecord(
        id=None,
        body=render_correction_report(
            task="HG-7",
            pr_number=7,
            reviewed_commit=reviewed,
            new_commit=new,
            cycle=cycle,
            tests="ok",
        ),
    )


def test_cycle_count_matches_completed_pairs_only():
    comments = [_review(SHA1)]
    assert completed_correction_cycles(comments) == 0
    comments.append(_correction(SHA1, SHA2, 1))
    assert completed_correction_cycles(comments) == 1
    comments.append(_review(SHA2))
    assert completed_correction_cycles(comments) == 1
    comments.append(_correction(SHA2, SHA3, 2))
    assert completed_correction_cycles(comments) == 2
    assert next_cycle_number(comments) == 3


def test_cycle_limit_is_three():
    comments = []
    shas = [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "cccccccccccccccccccccccccccccccccccccccc",
        "dddddddddddddddddddddddddddddddddddddddd",
    ]
    for index in range(3):
        comments.append(_review(shas[index]))
        comments.append(_correction(shas[index], shas[index + 1], index + 1))
    assert completed_correction_cycles(comments) == MAX_CORRECTION_CYCLES
    assert cycles_exhausted(comments) is True
