"""The homepage offers three doors. Ask is not the only way in."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


def test_homepage_has_three_distinct_doors():
    html = INDEX.read_text(encoding="utf-8")
    assert 'href="/me.html#upload?mode=manual"' in html
    assert 'href="/stack.html"' in html
    assert 'href="/ask.html"' in html
    doors = html.split('id="doors"', 1)[1].split("</div>", 1)[0]
    assert doors.count("<a ") == 3
    assert "Check my labs" in doors
    assert "Check my stack" in doors
    assert "Investigate a health problem" in doors
    assert "signup.html" not in doors
