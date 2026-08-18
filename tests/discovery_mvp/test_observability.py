"""PR-53: durable metrics, correlation ids, and provider circuit."""

from __future__ import annotations

import pytest

from app.discovery.observability import ProviderCircuit, load_metrics, persist_metrics
from app.discovery.telemetry import increment, reset


def test_metrics_survive_process_restart(tmp_path):
    reset()
    increment("scientific_output_blocked")
    path = tmp_path / "metrics.json"
    persist_metrics(path)
    reset()
    assert "scientific_output_blocked" not in __import__("app.discovery.telemetry", fromlist=["snapshot"]).snapshot()
    restored = load_metrics(path)
    assert restored["counters"]["scientific_output_blocked"] == 1


def test_provider_circuit_opens_after_failures():
    circuit = ProviderCircuit(failure_threshold=2)
    assert circuit.allow() is True
    circuit.record_failure()
    assert circuit.allow() is True
    circuit.record_failure()
    assert circuit.allow() is False
    circuit.record_success()
    assert circuit.allow() is True


@pytest.mark.asyncio
async def test_health_returns_correlation_id(client):
    response = await client.get("/health", headers={"x-request-id": "corr-test-1"})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "corr-test-1"
