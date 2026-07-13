"""Static frontend contract — biological systems + recommendations visibility hooks."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
_REPORT = Path(__file__).resolve().parents[2] / "frontend" / "report.html"


@pytest.fixture
def index_html() -> str:
    return _INDEX.read_text(encoding="utf-8")


@pytest.fixture
def report_html() -> str:
    return _REPORT.read_text(encoding="utf-8")


def test_index_html_exists():
    assert _INDEX.is_file()


def test_homepage_is_public_landing(index_html):
    assert "/login.html" in index_html
    assert "/signup.html" in index_html
    assert "Clinical biomarker intelligence" in index_html or "biological reasoning" in index_html
    assert 'id="recommendations"' not in index_html


def test_report_html_exists():
    assert _REPORT.is_file()


def test_report_sections_present(report_html):
    for section_id in (
        "executive-summary",
        "clinical-priorities",
        "diagnostic-optimization",
        "biological-network",
        "intervention-library",
        "patient-data",
        "research-appendix",
        "report-feedback",
    ):
        assert f'id="{section_id}"' in report_html


def test_biological_network_render_target(report_html):
    assert 'id="biological-network-body"' in report_html
    assert "biological-network-body" in report_html


def test_regenerate_and_operator_hint(report_html):
    assert 'id="regenerate-btn"' in report_html
    assert 'id="operator-hint"' in report_html
    assert "Regenerate Report" in report_html
    assert "localStorage" in report_html


def test_integrated_lab_analysis_ui(report_html):
    assert 'id="integrated-file-input"' in report_html
    assert 'id="integrated-analyze-btn"' in report_html
    assert "Integrated Lab Analysis" in report_html
    assert 'id="integrated-banner"' in report_html
    assert "/api/v1/analysis-sessions" in report_html


def test_intervention_library_and_sidebar(report_html):
    assert "Intervention Library" in report_html
    assert "intervention-library-body" in report_html
    assert "Clinical Priorities" in report_html
    assert "Executive Summary" in report_html
    assert "report-sidebar" in report_html
    assert "wallet-card" in report_html
    assert "Download Summary PDF" in report_html
    assert "/login.html" in report_html