#!/usr/bin/env python3
"""Headless Grok correction. Edits only the current checkout. Never merges."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

FORBIDDEN_PATH_PARTS = (".git", ".env", "id_rsa", "credentials")


def scrub_model_env(env: dict[str, str] | None = None) -> dict[str, str]:
    from agent_protocol.constants import PUSH_CREDENTIAL_KEYS

    source = dict(env if env is not None else os.environ)
    for key in PUSH_CREDENTIAL_KEYS:
        source.pop(key, None)
    return source


def path_is_allowed(repo_root: Path, raw: str) -> Path | None:
    from agent_protocol.control_plane import is_control_plane_path

    if not raw or raw.startswith("/") or ".." in Path(raw).parts:
        return None
    if is_control_plane_path(raw):
        return None
    target = (repo_root / raw).resolve()
    try:
        target.relative_to(repo_root.resolve())
    except ValueError:
        return None
    if any(part in FORBIDDEN_PATH_PARTS for part in target.parts):
        return None
    return target


def apply_file_edits(repo_root: Path, edits: list[dict]) -> list[str]:
    written: list[str] = []
    for edit in edits:
        target = path_is_allowed(repo_root, str(edit.get("path") or ""))
        if target is None:
            raise ValueError(f"forbidden_path:{edit.get('path')}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(edit.get("content") or ""), encoding="utf-8")
        written.append(str(target.relative_to(repo_root)))
    return written


def invoke_grok_cli(prompt_file: Path, repo_root: Path) -> int:
    grok = shutil.which("grok")
    if not grok:
        return 127
    return subprocess.call(
        [
            grok,
            "-p",
            "--permission-mode",
            "acceptEdits",
            "--prompt-file",
            str(prompt_file),
            "--cwd",
            str(repo_root),
        ],
        env=scrub_model_env(),
    )


def invoke_xai_file_edits(prompt: str, repo_root: Path) -> list[str]:
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("xai_api_key_missing")
    body = {
        "model": os.environ.get("XAI_MODEL", "grok-4"),
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return ONLY JSON {\"files\":[{\"path\":\"relative/path\",\"content\":\"...\"}]}. "
                    "Edit only files needed to satisfy the architect review. "
                    "Do not merge, deploy, create secrets, or change production."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"xai_http_{exc.code}") from exc
    content = payload["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < 0:
        raise RuntimeError("xai_output_not_json")
    parsed = json.loads(content[start : end + 1])
    return apply_file_edits(repo_root, list(parsed.get("files") or []))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: invoke_grok.py PROMPT_FILE [--repo DIR]", file=sys.stderr)
        return 2
    prompt_file = Path(sys.argv[1])
    repo_root = Path.cwd()
    if "--repo" in sys.argv:
        repo_root = Path(sys.argv[sys.argv.index("--repo") + 1])
    prompt = prompt_file.read_text(encoding="utf-8")
    code = invoke_grok_cli(prompt_file, repo_root)
    if code == 0:
        return 0
    if code != 127:
        return code
    try:
        written = invoke_xai_file_edits(prompt, repo_root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print("wrote " + ",".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
