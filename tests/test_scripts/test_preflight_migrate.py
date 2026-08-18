from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_alembic_has_single_accepted_head():
    raw = subprocess.check_output(["python3", "-m", "alembic", "heads"], cwd=ROOT, text=True)
    heads = [line.split()[0] for line in raw.splitlines() if line.strip()]
    assert heads == ["u6d7e8f9g0h1"]


def test_preflight_migrate_accepts_current_head():
    result = subprocess.run(
        ["python3", "scripts/preflight_migrate.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "preflight ok" in result.stdout


def test_v2_revision_is_archived_off_the_upgrade_path():
    live = ROOT / "alembic" / "versions"
    archive = ROOT / "alembic" / "versions_archive"
    assert not (live / "u1v2w3x4y5z6_discovery_investigation_state_v2.py").exists()
    assert (archive / "u1v2w3x4y5z6_discovery_investigation_state_v2.py").exists()
