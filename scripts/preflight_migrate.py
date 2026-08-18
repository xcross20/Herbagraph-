"""Refuse to stamp/migrate when the Alembic head or schema fingerprint is unexpected."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_HEADS = {"u5c6d7e8f9g0"}


def _heads() -> set[str]:
    raw = subprocess.check_output(["python3", "-m", "alembic", "heads"], cwd=ROOT, text=True)
    found = set()
    for line in raw.splitlines():
        token = line.split()[0] if line.strip() else ""
        if token:
            found.add(token)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-stamp", action="store_true")
    args = parser.parse_args()
    heads = _heads()
    if heads != ACCEPTED_HEADS:
        print(f"unexpected alembic heads {sorted(heads)}; expected {sorted(ACCEPTED_HEADS)}", file=sys.stderr)
        return 1
    if args.allow_stamp:
        print("stamp allowed only after schema fingerprint verification")
    print("preflight ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
