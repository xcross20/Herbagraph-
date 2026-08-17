"""Hard-deny automation control-plane paths. Do not rely on a prompt."""

from __future__ import annotations

from pathlib import Path

from .constants import CONTROL_PLANE_FILES, CONTROL_PLANE_PREFIXES


def normalize_repo_path(path: str) -> str:
    rel = str(path or "").replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel.lstrip("/")


def is_control_plane_path(path: str) -> bool:
    rel = normalize_repo_path(path)
    if not rel:
        return True
    if rel in CONTROL_PLANE_FILES:
        return True
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in CONTROL_PLANE_PREFIXES)


def untracked_paths(repo_root: Path) -> list[str]:
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_paths(repo_root: Path, *, base_sha: str | None = None) -> list[str]:
    import subprocess

    cmd = ["git", "diff", "--name-only"]
    if base_sha:
        cmd.append(base_sha)
    result = subprocess.run(cmd, cwd=repo_root, check=False, capture_output=True, text=True)
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    cached = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    names.extend(line.strip() for line in cached.stdout.splitlines() if line.strip())
    names.extend(untracked_paths(repo_root))
    return sorted(set(names))


_ALLOWED_FILE_TYPES = frozenset({"file", "missing"})


def unsafe_worktree_entries(repo_root: Path, paths: list[str]) -> list[str]:
    """Reject symlinks and unexpected types before git add -A."""
    root = repo_root.resolve()
    unsafe: list[str] = []
    for raw in paths:
        rel = normalize_repo_path(raw)
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            unsafe.append(f"escape:{rel}")
            continue
        if target.is_symlink() or (root / rel).is_symlink():
            unsafe.append(f"symlink:{rel}")
            continue
        if target.exists() and not target.is_file() and not target.is_dir():
            unsafe.append(f"special:{rel}")
    return unsafe


def forbidden_changes(paths: list[str]) -> list[str]:
    return [path for path in paths if is_control_plane_path(path)]


def assert_patch_allowed(repo_root: Path, *, expected_head: str) -> list[str]:
    """Fail closed if the untrusted worktree rewrote the control plane or committed."""
    import subprocess

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head.lower() != expected_head.lower():
        raise ValueError("untrusted_process_moved_head")
    paths = changed_paths(repo_root, base_sha=expected_head)
    forbidden = forbidden_changes(paths)
    if forbidden:
        raise ValueError("control_plane_edit:" + ",".join(forbidden))
    unsafe = unsafe_worktree_entries(repo_root, paths)
    if unsafe:
        raise ValueError("unsafe_worktree:" + ",".join(unsafe))
    return paths


def push_command(remote: str, head_ref: str) -> list[str]:
    if not head_ref.startswith("grok/"):
        raise ValueError("refusing_non_grok_push")
    return ["git", "push", remote, f"HEAD:refs/heads/{head_ref}"]
