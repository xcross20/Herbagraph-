"""The public page saves only when a session token is already present."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_signed_in_submit_uses_the_case_and_signed_out_stays_public():
    script = (ROOT / "frontend" / "js" / "stack-app.js").read_text()
    page = (ROOT / "frontend" / "stack.html").read_text()
    assert "/api/v1/cases/stack-check" in script
    assert "/api/v1/public/stack-check" in script
    assert "hg_tokens" in script
    assert "If you are not, nothing is stored." in page
