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
        "overall-confidence",
        "biological-reasoning",
        "patient-summary",
        "biological-systems",
        "evidence-overview",
        "recommendations",
        "differential-explanations",
        "missing-information",
        "patient-evidence-gaps",
        "report-methodology",
        "report-feedback",
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


def test_integrated_lab_analysis_ui(index_html):
    assert 'id="integrated-file-input"' in index_html
    assert 'id="integrated-analyze-btn"' in index_html
    assert "Integrated Lab Analysis" in index_html
    assert 'id="integrated-banner"' in index_html
    assert "/api/v1/analysis-sessions" in index_html


def test_recommendations_section_heading(index_html):
    assert "<h2>Evidence Synthesis</h2>" in index_html
    assert "Evidence Passport" in index_html
    assert "Missing Information" in index_html
    assert "hero-confidence" in index_html
    assert "visual-cascade" in index_html
    assert "Report Confidence" in index_html
    assert "Differential Biological Explanations" in index_html
    assert "Evidence Gaps" in index_html
    assert "rank-stars" in index_html
    assert "Applicable to" in index_html
    assert "How This Report Was Generated" in index_html
    assert "methodology-panel" in index_html
    assert '<summary>How This Report Was Generated</summary>' in index_html
    assert "Report Feedback" in index_html
    assert "patient encounter" in index_html.lower() or "patient encounter" in index_html