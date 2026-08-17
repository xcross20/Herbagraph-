"""Workflow and write-job isolation fixtures. These would have caught 36263b8 blockers."""

from __future__ import annotations

import json
from pathlib import Path

from agent_protocol.bootstrap import read_approved_bootstrap_sha, verify_trusted_sha
from agent_protocol.checks import apply_check_gate, parse_check_runs
from agent_protocol.commit_api import create_fast_forward_commit
from agent_protocol.manifest import collect_manifest, dump_manifest, load_manifest
from agent_protocol.trusted_path import assert_no_untrusted_modules, prepare_sys_path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/herbagraph-agent-loop.yml"
SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _workflow_section(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = f"  {name}:"
    start = text.index(marker)
    nxt = text.find("\n  ", start + len(marker))
    while nxt != -1 and not text[nxt + 3].isalpha():
        nxt = text.find("\n  ", nxt + 1)
    return text[start:nxt if nxt != -1 else None]


def test_correct_model_uploads_artifact_without_missing_plan_step():
    section = _workflow_section("correct-model")
    assert "id: plan" not in section
    assert "steps.plan.outputs.run_correction" not in section
    assert "upload-artifact" in section
    assert "name: correction-patch" in section
    assert "if: success()" in section


def test_commit_job_does_not_checkout_or_cd_into_untrusted():
    section = _workflow_section("commit")
    assert "path: untrusted" not in section
    assert "working-directory: untrusted" not in section
    assert "apply_commit.py" in section
    assert "validated-manifest.json" in section


def test_trusted_checkouts_use_qualify_exact_sha():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "trusted_sha: ${{ steps.pin.outputs.trusted_sha }}" in text
    assert "needs.qualify.outputs.trusted_sha" in text
    assert "TRUSTED_WORKFLOW_SHA: ${{ github.sha }}" not in text


def test_workflow_run_concurrency_is_pr_keyed():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "herbagraph-agent-loop-pr-${{ github.event.pull_request.number" in text
    assert "github.event.workflow_run.id" not in text.split("concurrency:", 1)[1][:400]


def test_lock_empty_accepts_resolved_default_branch_sha(tmp_path: Path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "agent-loop.lock").write_text("approved_bootstrap_sha=\n", encoding="utf-8")
    assert read_approved_bootstrap_sha(tmp_path) == ""
    assert verify_trusted_sha("abc", "") == "abc"


def test_lock_rejects_unrelated_sha(tmp_path: Path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "agent-loop.lock").write_text(f"approved_bootstrap_sha={SHA}\n", encoding="utf-8")
    try:
        verify_trusted_sha(OTHER, read_approved_bootstrap_sha(tmp_path))
        raise AssertionError("unrelated sha must fail")
    except ValueError as exc:
        assert "unapproved_orchestrator_sha" in str(exc)


def test_write_job_ignores_shadow_modules_in_untrusted_tree(tmp_path: Path):
    untrusted = tmp_path / "untrusted"
    untrusted.mkdir()
    (untrusted / "json.py").write_text("raise RuntimeError('shadow-json')\n", encoding="utf-8")
    (untrusted / "trusted").mkdir()
    (untrusted / "trusted" / "scripts").mkdir()
    (untrusted / "trusted" / "scripts" / "agent_protocol").mkdir()
    (untrusted / "trusted" / "scripts" / "agent_protocol" / "commit_api.py").write_text(
        "raise RuntimeError('shadow-commit')\n", encoding="utf-8"
    )
    trusted = ROOT / "scripts"
    prepare_sys_path(trusted, forbidden_roots=[untrusted])
    assert_no_untrusted_modules([untrusted])
    from agent_protocol.commit_api import assert_grok_ref

    assert assert_grok_ref("grok/x") == "grok/x"


def test_e2e_pending_then_manifest_then_api_commit(tmp_path: Path):
    pending = parse_check_runs({"check_runs": [{"name": "gates", "status": "in_progress"}]})
    assert apply_check_gate("CHANGES_REQUIRED", pending)["write"] == "false"

    repo = tmp_path / "tree"
    repo.mkdir()
    target = repo / "tests" / "fixtures"
    target.mkdir(parents=True)
    (target / "ok.bin").write_bytes(b"\x00\x01\xffhello")
    manifest = collect_manifest(repo, ["tests/fixtures/ok.bin"], parent_sha=SHA)
    dumped = dump_manifest(manifest)
    (tmp_path / "validated-manifest.json").write_text(json.dumps(dumped), encoding="utf-8")
    loaded = load_manifest(tmp_path / "validated-manifest.json")
    assert loaded.files[0].content == b"\x00\x01\xffhello"

    calls = []

    def fake_request(method, url, token, payload=None):
        calls.append((method, url, payload))
        if method == "GET" and url.endswith("/git/ref/heads/grok/7-x"):
            return {"object": {"sha": SHA}}
        if method == "GET" and "/git/commits/" in url:
            return {"tree": {"sha": "tree0"}}
        if method == "POST" and url.endswith("/git/blobs"):
            return {"sha": "blob1"}
        if method == "POST" and url.endswith("/git/trees"):
            return {"sha": "tree1"}
        if method == "POST" and url.endswith("/git/commits"):
            return {"sha": OTHER}
        if method == "PATCH":
            assert payload["force"] is False
            return {}
        raise AssertionError((method, url))

    files = {item.path: (item.mode, item.content) for item in loaded.files}
    result = create_fast_forward_commit(
        api_root="https://api.github.com/repos/o/r",
        token="t",
        head_ref="grok/7-x",
        expected_parent=SHA,
        files=files,
        deletions=[],
        message="fix",
        request=fake_request,
    )
    assert result.sha == OTHER
    assert any(method == "PATCH" for method, _, _ in calls)
