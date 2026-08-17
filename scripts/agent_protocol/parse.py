"""Parse durable GitHub comments into protocol records."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .constants import (
    COMMENT_MARKER_PREFIX,
    CORRECTION_HEADING,
    CORRECTION_MARKER_PREFIX,
    HANDOFF_HEADING,
    HANDOFF_MARKER_PREFIX,
    REVIEW_HEADING,
    VERDICTS,
)

_SHA_RE = re.compile(r"\b([0-9a-f]{40})\b", re.IGNORECASE)
_STATUS_RE = re.compile(r"^Status:\s*(\S+)\s*$", re.MULTILINE | re.IGNORECASE)
_REVIEWED_RE = re.compile(r"^Reviewed commit:\s*(\S+)\s*$", re.MULTILINE | re.IGNORECASE)
_COMMIT_RE = re.compile(r"^Commit:\s*(\S+)\s*$", re.MULTILINE | re.IGNORECASE)
_CYCLE_RE = re.compile(r"^Correction-cycle:\s*(\d+)\s*$", re.MULTILINE | re.IGNORECASE)
_TASK_RE = re.compile(r"^Task:\s*(\S+)\s*$", re.MULTILINE | re.IGNORECASE)
_OWNER_RE = re.compile(r"^Next owner:\s*(\S+)\s*$", re.MULTILINE | re.IGNORECASE)
_SECTION_RE = re.compile(
    r"^(BLOCKING|SHOULD-FIX|NOTED|HOSTILE TRACE|REQUIRED CHECKS|ALLOWED NEXT SCOPE|TRAP LINE):\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ArchitectReview:
    task: str
    reviewed_commit: str
    status: str
    blocking: tuple[str, ...] = ()
    should_fix: tuple[str, ...] = ()
    noted: tuple[str, ...] = ()
    hostile_trace: str = ""
    required_checks: tuple[str, ...] = ()
    allowed_next_scope: str = ""
    next_owner: str = ""
    trap_line: str = ""
    raw: str = ""

    @property
    def idempotency_key(self) -> str:
        return f"{self.reviewed_commit}:{self.status}"


@dataclass(frozen=True)
class ImplementationHandoff:
    task: str
    commit: str
    status: str
    raw: str = ""


@dataclass(frozen=True)
class CorrectionReport:
    task: str
    reviewed_commit: str
    new_commit: str
    cycle: int
    raw: str = ""


@dataclass
class CommentRecord:
    id: int | None
    body: str
    marker: str | None = None
    author_login: str = ""
    author_type: str = ""


def extract_full_sha(text: str | None) -> str | None:
    if not text:
        return None
    match = _SHA_RE.search(text)
    return match.group(1).lower() if match else None


def parse_verdict(text: str | None) -> str | None:
    if not text:
        return None
    match = _STATUS_RE.search(text)
    if not match:
        return None
    value = match.group(1).strip().upper().replace(" ", "_")
    if value in VERDICTS:
        return value
    return None


def _section_items(body: str, heading: str) -> tuple[str, ...]:
    parts = _SECTION_RE.split(body)
    items: list[str] = []
    for index, part in enumerate(parts):
        if part == heading and index + 1 < len(parts):
            block = parts[index + 1]
            for line in block.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith(("#", "HERBAGRAPH_")):
                    break
                items.append(re.sub(r"^[\-\d\.\)\s]+", "", stripped).strip())
            break
    return tuple(item for item in items if item)


def _section_text(body: str, heading: str) -> str:
    items = _section_items(body, heading)
    return " ".join(items).strip()


def parse_architect_review(
    body: str,
    *,
    expected_marker: str | None = None,
    expected_sha: str | None = None,
    expected_task: str | None = None,
) -> ArchitectReview | None:
    if REVIEW_HEADING not in (body or ""):
        return None
    if expected_marker and expected_marker not in body:
        return None
    status = parse_verdict(body)
    reviewed_match = _REVIEWED_RE.search(body or "")
    if not reviewed_match:
        return None
    reviewed = extract_full_sha(reviewed_match.group(1))
    if not status or not reviewed:
        return None
    if expected_sha and reviewed != expected_sha.lower():
        return None
    task_match = _TASK_RE.search(body)
    task = task_match.group(1) if task_match else ""
    if expected_task and task != expected_task:
        return None
    if not task:
        return None
    owner_match = _OWNER_RE.search(body)
    return ArchitectReview(
        task=task,
        reviewed_commit=reviewed,
        status=status,
        blocking=_section_items(body, "BLOCKING"),
        should_fix=_section_items(body, "SHOULD-FIX"),
        noted=_section_items(body, "NOTED"),
        hostile_trace=_section_text(body, "HOSTILE TRACE"),
        required_checks=_section_items(body, "REQUIRED CHECKS"),
        allowed_next_scope=_section_text(body, "ALLOWED NEXT SCOPE"),
        next_owner=(owner_match.group(1).upper() if owner_match else ""),
        trap_line=_section_text(body, "TRAP LINE"),
        raw=body,
    )


def parse_handoff(body: str) -> ImplementationHandoff | None:
    if HANDOFF_HEADING not in (body or ""):
        return None
    commit_match = _COMMIT_RE.search(body)
    if not commit_match:
        return None
    commit = extract_full_sha(commit_match.group(1))
    if not commit:
        return None
    task_match = _TASK_RE.search(body)
    status_match = _STATUS_RE.search(body)
    return ImplementationHandoff(
        task=(task_match.group(1) if task_match else "UNKNOWN"),
        commit=commit,
        status=(status_match.group(1) if status_match else ""),
        raw=body,
    )


def parse_correction_report(body: str) -> CorrectionReport | None:
    if CORRECTION_HEADING not in (body or ""):
        return None
    cycle_match = _CYCLE_RE.search(body)
    shas = _SHA_RE.findall(body or "")
    if not cycle_match or len(shas) < 1:
        return None
    reviewed = shas[0].lower()
    new_commit = shas[1].lower() if len(shas) > 1 else reviewed
    task_match = _TASK_RE.search(body)
    return CorrectionReport(
        task=(task_match.group(1) if task_match else "UNKNOWN"),
        reviewed_commit=reviewed,
        new_commit=new_commit,
        cycle=int(cycle_match.group(1)),
        raw=body,
    )


def parse_review_json(payload: str) -> ArchitectReview | None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    status = str(data.get("status") or "").upper().replace(" ", "_")
    reviewed = extract_full_sha(str(data.get("reviewed_commit") or ""))
    if status not in VERDICTS or not reviewed:
        return None

    def _list(key: str) -> tuple[str, ...]:
        value = data.get(key) or []
        if isinstance(value, str):
            return (value,) if value.strip() else ()
        return tuple(str(item) for item in value if str(item).strip())

    return ArchitectReview(
        task=str(data.get("task") or "UNKNOWN"),
        reviewed_commit=reviewed,
        status=status,
        blocking=_list("blocking"),
        should_fix=_list("should_fix"),
        noted=_list("noted"),
        hostile_trace=str(data.get("hostile_trace") or ""),
        required_checks=_list("required_checks"),
        allowed_next_scope=str(data.get("allowed_next_scope") or ""),
        next_owner=str(data.get("next_owner") or "").upper(),
        trap_line=str(data.get("trap_line") or ""),
        raw=payload,
    )


def marker_for_review(pr_number: int, sha: str) -> str:
    return f"{COMMENT_MARKER_PREFIX} idempotency={pr_number}-{sha} -->"


def marker_for_correction(pr_number: int, sha: str) -> str:
    return f"{CORRECTION_MARKER_PREFIX} idempotency={pr_number}-{sha} -->"


def marker_for_handoff(pr_number: int, sha: str) -> str:
    return f"{HANDOFF_MARKER_PREFIX} idempotency={pr_number}-{sha} -->"


def find_comment_with_marker(comments: list[CommentRecord], marker: str) -> CommentRecord | None:
    for comment in comments:
        if marker in (comment.body or ""):
            return comment
    return None
