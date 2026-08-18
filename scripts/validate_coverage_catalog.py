"""Reject duplicate, contradictory, circular, or provenance-free coverage rules."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.discovery.coverage_validation import validate_coverage_catalog  # noqa: E402


def main() -> int:
    result = validate_coverage_catalog()
    if not result.accepted:
        print("coverage catalog invalid:", *result.errors, sep="\n  ", file=sys.stderr)
        return 1
    print(f"coverage catalog {result.version} accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
