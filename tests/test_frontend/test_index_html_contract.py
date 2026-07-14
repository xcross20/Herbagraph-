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
    assert "HerbaGraph" in index_html
    assert "logo-mark" in index_html
    assert "#2f7df6" in index_html
    assert 'id="recommendations"' not in index_html
    assert "landing-hero" in index_html
    assert "/mock/" not in index_html
    assert "product-mock" not in index_html
    assert "/report.html?demo=1" in index_html
    assert "embed=1" in index_html
    assert "product-live-iframe" in index_html
    assert "View sample report" in index_html
    assert "/css/landing.css" in index_html
    assert "HerbaGraph connects the system behind them" in index_html
    assert "hero-eyebrow" in index_html
    assert "Connected biological intelligence" in index_html
    assert "Connected biological intelligence for personalized health analysis" in index_html
    assert "Clinical disclaimer" in index_html
    assert "AI Clinical Reasoning for Precision Nutrition" not in index_html
    assert "biology-atmosphere.jpg" in index_html
    assert "biology-atlas-plate.jpg" in index_html
    assert "Biology does not operate in isolation" in index_html
    assert "42374454" in index_html


def test_landing_visual_assets_exist():
    assets = Path(__file__).resolve().parents[2] / "frontend" / "assets"
    assert (assets / "biology-atmosphere.jpg").is_file()
    assert (assets / "biology-atlas-plate.jpg").is_file()


def test_signup_requires_access_code_field():
    html = (Path(__file__).resolve().parents[2] / "frontend" / "signup.html").read_text(encoding="utf-8")
    assert 'id="auth-access-code"' in html
    assert 'id="auth-access-wrap"' in html
    assert "/css/auth.css" in html
    assert 'name="account-type"' in html
    assert "Create your HerbaGraph account" in html
    assert "verify-signup-access" in (Path(__file__).resolve().parents[2] / "frontend" / "js" / "herbagraph-auth.js").read_text(
        encoding="utf-8"
    )


def test_login_auth_redesign():
    html = (Path(__file__).resolve().parents[2] / "frontend" / "login.html").read_text(encoding="utf-8")
    assert "/css/auth.css" in html
    assert "auth-page-v2" in html
    assert "Sign in to HerbaGraph" in html
    assert "See the system behind the data" in html
    assert "google-login-btn" in html
    assert "signInWithGoogle" in (Path(__file__).resolve().parents[2] / "frontend" / "js" / "herbagraph-auth.js").read_text(
        encoding="utf-8"
    )
    assert "verify-access-code" in (Path(__file__).resolve().parents[2] / "frontend" / "js" / "herbagraph-auth.js").read_text(
        encoding="utf-8"
    )


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
    assert "Regenerate report" in report_html


def test_sample_report_assets_exist():
    sample = Path(__file__).resolve().parents[2] / "frontend" / "data" / "sample-clinical-report.json"
    assert sample.is_file()
    data = sample.read_text(encoding="utf-8")
    assert "executive_summary" in data
    assert "recommendations" in data


def test_report_demo_mode_hooks(report_html):
    assert 'id="demo-banner"' in report_html
    assert "loadSampleReport" in report_html
    assert 'urlParams.get("demo") === "1"' in report_html
    assert "/data/sample-clinical-report.json" in report_html
    assert "isEmbedMode" in report_html
    assert "report-embed" in report_html
    assert 'Research tool, not medical advice' not in report_html
    assert "Analysis confidence ·" not in report_html


def test_report_workspace_shell(report_html):
    assert 'id="nav-logo"' in report_html
    assert "brand-logo.js" in report_html
    assert "reasoning-graph.js" in report_html
    assert "/css/report.css" in report_html
    assert "/css/site.css" in report_html
    assert "report-outline" in report_html
    assert 'id="report-empty"' in report_html
    assert 'href="/app.html#dashboard"' in report_html
    assert 'id="integrated-banner"' in report_html
    assert 'id="upload-section"' not in report_html
    assert 'id="analyze-btn"' not in report_html


def test_intervention_library_and_sidebar(report_html):
    assert "Intervention Library" in report_html
    assert "intervention-library-body" in report_html
    assert "Clinical Priorities" in report_html
    assert "Executive Summary" in report_html
    assert "report-sidebar" in report_html
    assert "wallet-card" in report_html
    assert "Download Summary PDF" in report_html
    assert "/login.html" in report_html