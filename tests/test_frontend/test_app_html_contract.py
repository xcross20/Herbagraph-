from pathlib import Path

_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "app.html"


def test_app_html_serves_workspace_shell():
    html = _INDEX.read_text(encoding="utf-8")
    assert "/api/v1/workspace/dashboard" in html
    assert "/api/v1/analysis-sessions" in html
    assert "link-labs" in html
    assert "#dashboard" in html
    assert "/login.html" in html
    assert "/report.html" in html
    assert "brand-logo.js" in html
    assert "app-nav-logo" in html