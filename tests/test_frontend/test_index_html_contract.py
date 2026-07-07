"""Static frontend contract — biological systems + recommendations visibility hooks."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


@pytest.fixture
def index_html() -> str:
    return _INDEX.read_text(encoding="utf-8")


def test_index_html_exists():
    assert _INDEX.is_file()


def test_report_sections_present(index_html):
    for section_id in (
        "patient-summary",
        "biological-systems",
        "recommendations",
        "profile-biomarkers",
    ):
        assert f'id="{section_id}"' in index_html


def test_biological_systems_render_target(index_html):
    assert 'id="biological-systems-body"' in index_html
    assert "biological-systems-body" in index_html


def test_regenerate_and_operator_hint(index_html):
    assert 'id="regenerate-btn"' in index_html
    assert 'id="operator-hint"' in index_html
    assert "Regenerate Report" in index_html
    assert "localStorage" in index_html


def test_recommendations_section_heading(index_html):
    assert "<h2>Recommendations</h2>" in index_html