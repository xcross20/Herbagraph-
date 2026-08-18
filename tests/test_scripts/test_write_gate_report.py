from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from write_gate_report import main  # noqa: E402


def test_gate_report_names_exact_sha(tmp_path: Path, monkeypatch):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<?xml version="1.0"?>
<testsuite tests="2" failures="0" errors="0" skipped="0">
  <testcase classname="t" name="a"/>
  <testcase classname="t" name="b"/>
</testsuite>
""",
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    monkeypatch.setattr(
        "sys.argv",
        ["write_gate_report.py", "--junit", str(junit), "--out", str(out), "--sha", sha],
    )
    assert main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["head_sha"] == sha
    assert report["tests"] == 2
    assert report["conclusion"] == "pass"
