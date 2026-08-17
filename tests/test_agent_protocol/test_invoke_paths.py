from pathlib import Path

from agent_protocol.invoke_grok import apply_file_edits, path_is_allowed


def test_rejects_escaped_and_secret_paths(tmp_path: Path):
    assert path_is_allowed(tmp_path, "../outside") is None
    assert path_is_allowed(tmp_path, "/etc/passwd") is None
    assert path_is_allowed(tmp_path, ".env") is None
    allowed = path_is_allowed(tmp_path, "docs/note.md")
    assert allowed == (tmp_path / "docs/note.md").resolve()


def test_applies_only_safe_relative_edits(tmp_path: Path):
    written = apply_file_edits(tmp_path, [{"path": "docs/note.md", "content": "ok\n"}])
    assert written == ["docs/note.md"]
    assert (tmp_path / "docs/note.md").read_text(encoding="utf-8") == "ok\n"
