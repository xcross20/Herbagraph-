"""Tests for PMID integrity audit script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_audit_pmid_integrity_denylist_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_pmid_integrity.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All mandatory PMID integrity checks passed" in result.stdout