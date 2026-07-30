from pathlib import Path

_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "app.html"


def test_app_html_serves_workspace_shell():
    html = _INDEX.read_text(encoding="utf-8")
    assert "/api/v1/workspace/dashboard" in html
    assert "/api/v1/analysis-sessions" in html
    assert "link-labs" in html
    assert "#dashboard" in html
    assert "#reports" in html
    assert "/login.html" in html
    assert "/report.html" in html
    assert "brand-logo.js" in html
    assert "app-nav-logo" in html
    assert "/css/app.css" in html
    assert "app-sidebar" in html
    assert "Needs attention" in html
    assert "reasoning-graph.js" in html
    assert "mountAnalysisGraph" in html
    assert "knowledge-path-picker.js" in html
    assert "hgPickKnowledgePath" in html
    assert "knowledge_path" in html
    # Mobile navigation shell
    assert 'id="mobile-nav-toggle"' in html
    assert 'id="mobile-topbar"' in html
    assert 'id="sidebar-backdrop"' in html
    assert "wireMobileNav" in html
    assert "setSidebarOpen" in html
    assert "showAppError" in html
    # Auth callback must continue into render (not early-return blank gray screen)
    assert "await Auth.handleAuthRedirect()" in html
    assert "if (await Auth.handleAuthRedirect())" not in html
    assert "showAppError(err)" in html
    assert 'name="viewport"' in html