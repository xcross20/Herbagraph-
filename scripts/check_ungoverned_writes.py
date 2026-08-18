"""Fail if DiscoveryFinding is constructed outside the mutation seam."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    ROOT / "app" / "discovery" / "mutations.py",
    ROOT / "app" / "discovery" / "commands.py",
}


def main() -> int:
    hits: list[str] = []
    for path in (ROOT / "app").rglob("*.py"):
        if path in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        for index, line in enumerate(text.splitlines(), start=1):
            if "DiscoveryFinding(" in line and not line.lstrip().startswith("class "):
                hits.append(f"{path.relative_to(ROOT)}:{index}")
    if hits:
        print("ungoverned DiscoveryFinding writes:", *hits, sep="\n  ", file=sys.stderr)
        return 1
    print("no ungoverned DiscoveryFinding writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
