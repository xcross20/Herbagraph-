"""CI gate: pipeline resilience audit."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_audit_pipeline_resilience_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_pipeline_resilience.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "450 probes" in result.stdout or "probes" in result.stdout