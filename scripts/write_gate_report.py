"""Write a machine-readable CI gate report for the exact tested SHA."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def _git_sha() -> str:
    raw = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    return raw.lower()


def _parse_junit(path: Path) -> dict:
    if not path.exists():
        return {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "skipped_names": []}
    tree = ET.parse(path)
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = failures = errors = skipped = 0
    skipped_names: list[str] = []
    for suite in suites:
        tests += int(suite.attrib.get("tests") or 0)
        failures += int(suite.attrib.get("failures") or 0)
        errors += int(suite.attrib.get("errors") or 0)
        skipped += int(suite.attrib.get("skipped") or 0)
        for case in suite.findall("testcase"):
            if case.find("skipped") is not None:
                skipped_names.append(f"{case.attrib.get('classname')}::{case.attrib.get('name')}")
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "skipped_names": skipped_names,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sha", default="")
    parser.add_argument("--command", default="pytest tests/")
    args = parser.parse_args()
    sha = (args.sha or _git_sha()).strip().lower()
    if len(sha) < 40:
        print("head sha must be full 40 characters", file=sys.stderr)
        return 1
    counts = _parse_junit(Path(args.junit))
    report = {
        "head_sha": sha,
        "command": args.command,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conclusion": "pass" if counts["failures"] == 0 and counts["errors"] == 0 else "fail",
        **counts,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["conclusion"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
