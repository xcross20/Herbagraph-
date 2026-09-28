"""The saved report page can compare a later number without calling it a cause."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_case_report_posts_a_follow_up_compare():
    page = (ROOT / "frontend" / "case-report.html").read_text()
    script = (ROOT / "frontend" / "js" / "case-report.js").read_text()
    assert "A change is not a cause." in page
    assert "/follow-up" in script
    assert "esc(" in script
