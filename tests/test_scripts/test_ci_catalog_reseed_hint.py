"""Tests for CI catalog reseed hint helper."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_ci_catalog_reseed_hint_exits_zero():
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "ci_catalog_reseed_hint.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "reseed" in result.stdout.lower()


def test_ci_reseed_postgres_skips_without_catalog_changes():
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "ci_reseed_postgres.sh"), head],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "skipped" in result.stdout.lower() or "skip" in result.stdout.lower()