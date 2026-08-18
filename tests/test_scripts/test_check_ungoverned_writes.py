from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_ungoverned_finding_writes():
    result = subprocess.run(
        ["python3", "scripts/check_ungoverned_writes.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
