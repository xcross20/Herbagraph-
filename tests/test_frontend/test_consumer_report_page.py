"""The saved report page reads the case and escapes what it prints."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_stack_receipt_links_to_the_saved_report():
    script = (ROOT / "frontend" / "js" / "stack-app.js").read_text()
    page = (ROOT / "frontend" / "js" / "case-report.js").read_text()
    assert "/case-report.html?case=" in script
    assert "/api/v1/cases/" in page
    assert "/report" in page
    assert "esc(" in page
    assert "hg_tokens" in page
