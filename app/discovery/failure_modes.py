"""Explicit partial/failed outcomes. Never convert injection faults into success."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TurnOutcome:
    status: str  # succeeded | partial | failed
    detail: str
    payload: dict[str, Any] | None = None


def recover_json(raw: str) -> TurnOutcome:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        repaired = raw.strip().rstrip(",")
        if repaired.startswith("{") and not repaired.endswith("}"):
            repaired += "}"
        try:
            payload = json.loads(repaired)
        except json.JSONDecodeError:
            return TurnOutcome("failed", f"malformed_json:{exc.msg}", None)
        return TurnOutcome("partial", "repaired_json", payload if isinstance(payload, dict) else None)
    if not isinstance(payload, dict):
        return TurnOutcome("failed", "json_not_object", None)
    return TurnOutcome("succeeded", "ok", payload)


def llm_timeout() -> TurnOutcome:
    return TurnOutcome("failed", "llm_timeout", None)


def document_parse_incomplete(*, parsed_rows: int, expected_rows: int) -> TurnOutcome:
    if parsed_rows <= 0:
        return TurnOutcome("failed", "document_parse_empty", None)
    if parsed_rows < expected_rows:
        return TurnOutcome("partial", "document_parse_incomplete", {"parsed_rows": parsed_rows})
    return TurnOutcome("succeeded", "ok", {"parsed_rows": parsed_rows})


def commit_without_response() -> TurnOutcome:
    return TurnOutcome("partial", "committed_response_unsent", None)
