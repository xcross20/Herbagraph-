"""Keep write-token and orchestrator Python off the PR worktree."""

from __future__ import annotations

import sys
from pathlib import Path


def prepare_sys_path(trusted_scripts: Path, *, forbidden_roots: list[Path] | None = None) -> list[str]:
    """Use only the trusted scripts dir plus non-forbidden existing entries."""
    trusted = trusted_scripts.resolve()
    forbidden = [path.resolve() for path in (forbidden_roots or [])]
    cleaned: list[str] = [str(trusted)]
    for entry in sys.path:
        if entry in ("", "."):
            continue
        try:
            resolved = Path(entry).resolve()
        except OSError:
            continue
        if resolved == Path.cwd().resolve():
            continue
        if any(resolved == root or root in resolved.parents or resolved in root.parents for root in forbidden):
            continue
        if resolved == trusted:
            continue
        cleaned.append(str(resolved))
    sys.path[:] = cleaned
    return cleaned


def assert_no_untrusted_modules(forbidden_roots: list[Path]) -> None:
    roots = [path.resolve() for path in forbidden_roots]
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        try:
            resolved = Path(filename).resolve()
        except OSError:
            continue
        if any(resolved == root or root in resolved.parents for root in roots):
            raise RuntimeError(f"untrusted_module_loaded:{name}:{resolved}")
