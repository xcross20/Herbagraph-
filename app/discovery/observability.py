"""Durable, PHI-safe Discovery signals. In-process counters are not enough."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from app.discovery.telemetry import increment, snapshot

DEFAULT_PATH = Path(os.environ.get("HERBAGRAPH_METRICS_PATH") or "/tmp/herbagraph-discovery-metrics.json")

CORRECTNESS_SIGNALS = (
    "duplicate_active_findings",
    "inactive_finding_exposed_as_active",
    "missing_predecessor",
    "unrelated_evidence_edge",
    "branch_closed_without_direct_evidence",
    "unknown_coverage_as_negative",
    "scientific_output_blocked",
    "parser_false_success",
    "safety_escalation_lost",
    "idempotency_conflict",
)


def correlation_id() -> str:
    return uuid.uuid4().hex


def persist_metrics(path: Path | None = None) -> Path:
    target = path or DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": time.time(), "counters": snapshot(), "signals": list(CORRECTNESS_SIGNALS)}
    target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return target


def load_metrics(path: Path | None = None) -> dict:
    target = path or DEFAULT_PATH
    if not target.exists():
        return {"counters": {}, "signals": list(CORRECTNESS_SIGNALS)}
    return json.loads(target.read_text(encoding="utf-8"))


class ProviderCircuit:
    def __init__(self, *, failure_threshold: int = 3, timeout_seconds: float = 12.0):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.open = False

    def record_failure(self) -> None:
        self.failures += 1
        increment("provider_failure")
        if self.failures >= self.failure_threshold:
            self.open = True
            increment("provider_circuit_open")

    def record_success(self) -> None:
        self.failures = 0
        self.open = False

    def allow(self) -> bool:
        return not self.open
