from pathlib import Path

from agent_protocol.invoke_grok import apply_file_edits, extract_files_payload, path_is_allowed


def test_rejects_escaped_and_secret_paths(tmp_path: Path):
    assert path_is_allowed(tmp_path, "../outside") is None
    assert path_is_allowed(tmp_path, "/etc/passwd") is None
    assert path_is_allowed(tmp_path, ".env") is None
    allowed = path_is_allowed(tmp_path, "docs/note.md")
    assert allowed == (tmp_path / "docs/note.md").resolve()


def test_extracts_files_json_from_fenced_model_output():
    parsed = extract_files_payload(
        '```json\n{"files":[{"path":"tests/fixtures/agent_loop_canary.txt","content":"canary-ready\\n"}]}\n```'
    )
    assert parsed["files"][0]["content"] == "canary-ready\n"


def test_applies_only_safe_relative_edits(tmp_path: Path):
    written = apply_file_edits(tmp_path, [{"path": "docs/note.md", "content": "ok\n"}])
    assert written == ["docs/note.md"]
    assert (tmp_path / "docs/note.md").read_text(encoding="utf-8") == "ok\n"


def test_applies_edits_when_repo_root_is_relative(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "untrusted").mkdir()
    written = apply_file_edits(Path("untrusted"), [{"path": "tests/fixtures/agent_loop_canary.txt", "content": "canary-ready\n"}])
    assert written == ["tests/fixtures/agent_loop_canary.txt"]
    assert (tmp_path / "untrusted" / "tests" / "fixtures" / "agent_loop_canary.txt").read_text(encoding="utf-8") == "canary-ready\n"
