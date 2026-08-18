"""Issue 58/64: successive turns share one incrementing snapshot_id."""

from __future__ import annotations

from app.discovery.orchestrator import orchestrate


def test_successive_turns_increment_shared_snapshot(monkeypatch):
    monkeypatch.setattr("app.discovery.usefulness.usefulness_governor_enabled", lambda: True)
    prior = {}
    control = None
    versions = []
    for text in (
        "There is mild discomfort under my right ribs after fatty meals.",
        "yeah after fatty foods, ive been wondering if theres any thing i can do for relief before getting some of these tests",
        "yeah possibly but what can i do now?",
    ):
        last = orchestrate(text, prior_facts=prior, asked=[], answered=set(), control_state=control)
        for item in last.new_findings:
            prior[item.name] = item.value or ""
        control = last.control
        snap = control.get("snapshot_id")
        extras = last.action.extras or {}
        versions.append(control.get("case_version"))
        assert snap == f"cv{control.get('case_version')}"
        if extras.get("snapshot_id"):
            assert extras["snapshot_id"] == snap
        if extras.get("explanation"):
            assert extras["explanation"].get("snapshot_id") == snap
        if extras.get("action_plan"):
            assert extras["action_plan"].get("snapshot_id") == snap
    assert versions == sorted(versions)
    assert versions[-1] > versions[0]
    assert len(set(versions)) == 3
