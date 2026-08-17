"""Validated file manifest. The write job treats this as data, not a worktree."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

ALLOWED_MODES = frozenset({"100644", "100755"})


@dataclass(frozen=True)
class FileEntry:
    path: str
    mode: str
    content: bytes


@dataclass(frozen=True)
class ValidatedManifest:
    parent_sha: str
    files: tuple[FileEntry, ...]
    deletions: tuple[str, ...]


def collect_manifest(repo_root: Path, paths: list[str], *, parent_sha: str) -> ValidatedManifest:
    files: list[FileEntry] = []
    deletions: list[str] = []
    root = repo_root.resolve()
    for raw in paths:
        rel = raw.replace("\\", "/").lstrip("./")
        target = (root / rel)
        if target.is_symlink():
            raise ValueError(f"symlink:{rel}")
        if not target.exists():
            deletions.append(rel)
            continue
        if not target.is_file():
            raise ValueError(f"unsupported_type:{rel}")
        mode = "100755" if target.stat().st_mode & 0o111 else "100644"
        if mode not in ALLOWED_MODES:
            raise ValueError(f"unsupported_mode:{rel}:{mode}")
        files.append(FileEntry(path=rel, mode=mode, content=target.read_bytes()))
    return ValidatedManifest(parent_sha=parent_sha.lower(), files=tuple(files), deletions=tuple(deletions))


def dump_manifest(manifest: ValidatedManifest) -> dict:
    return {
        "parent_sha": manifest.parent_sha,
        "files": [
            {
                "path": item.path,
                "mode": item.mode,
                "content_base64": base64.b64encode(item.content).decode("ascii"),
            }
            for item in manifest.files
        ],
        "deletions": list(manifest.deletions),
    }


def load_manifest(path: Path) -> ValidatedManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    files = []
    for item in raw.get("files") or []:
        mode = str(item.get("mode") or "100644")
        if mode not in ALLOWED_MODES:
            raise ValueError(f"unsupported_mode:{item.get('path')}:{mode}")
        files.append(
            FileEntry(
                path=str(item["path"]),
                mode=mode,
                content=base64.b64decode(item["content_base64"]),
            )
        )
    return ValidatedManifest(
        parent_sha=str(raw["parent_sha"]).lower(),
        files=tuple(files),
        deletions=tuple(str(item) for item in (raw.get("deletions") or [])),
    )
