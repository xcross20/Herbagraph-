"""CI gate: unresolved abnormal biomarker audit."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_audit_unresolved_abnormals_passes_on_current_matrix():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_unresolved_abnormals.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_blindspot_fixtures_list_is_non_empty():
    mod = importlib.import_module("scripts.audit_unresolved_abnormals")
    assert len(mod.BLINDSPOT_FIXTURES) >= 2
    for path in mod.BLINDSPOT_FIXTURES:
        assert path.exists(), path