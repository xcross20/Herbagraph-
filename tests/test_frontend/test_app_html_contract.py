from pathlib import Path

_APP_JS = Path(__file__).resolve().parents[2] / "frontend" / "js" / "workspace-app.js"
_CLINIC = Path(__file__).resolve().parents[2] / "frontend" / "clinic.html"


def test_app_html_serves_workspace_shell():
    html = _CLINIC.read_text(encoding="utf-8")
    js = _APP_JS.read_text(encoding="utf-8")
    assert "/api/v1/workspace/dashboard" in js
    assert "/api/v1/analysis-sessions" in js
    assert "link-labs" in js
    assert "#dashboard" in html
    assert "#reports" in html
    assert "/login.html" in js
    assert "/report.html" in js


def test_app_html_splits_clinician_and_consumer_workspace():
    html = _CLINIC.read_text(encoding="utf-8")
    js = _APP_JS.read_text(encoding="utf-8")
    assert "function isClinicianWorkspace()" in js
    assert "function applyWorkspaceChrome()" in js
    assert "function renderPatientScopeBar(" in js
    assert 'id="nav-patients-label"' in html
    assert 'id="patient-scope-select"' in js
    assert "/api/v1/cases?patient_id=" in js
    assert "Select a patient to open Discovery" in js
    assert "Working on <strong>your profile</strong>" in js
    assert "Next useful checks" in js
    assert 'hashBase === "upload"' in js or 'wirePatientScopeSelect("upload")' in js


def test_app_html_has_discovery_route():
    html = _CLINIC.read_text(encoding="utf-8")
    js = _APP_JS.read_text(encoding="utf-8")
    assert 'href="/ask.html"' in html
    assert 'location.replace(next.pathname + next.search)' in js
    assert "/ask.html" in js
    assert "/api/v1/cases" in js
    assert "brand-logo.js" in html
    assert "app-nav-logo" in html
    assert "/css/app.css" in html
    assert "app-sidebar" in html
    assert "Needs attention" in js
    assert "reasoning-graph.js" in html
    assert "mountAnalysisGraph" in js
    assert "knowledge-path-picker.js" in html
    assert "hgPickKnowledgePath" in js
    assert "knowledge_path" in js
    # Mobile navigation shell
    assert 'id="mobile-nav-toggle"' in html
    assert 'id="mobile-topbar"' in html
    assert 'id="sidebar-backdrop"' in html
    assert "wireMobileNav" in js
    assert "setSidebarOpen" in js
    assert "showAppError" in js
    # Auth callback must continue into render (not early-return blank gray screen)
    assert "await Auth.handleAuthRedirect()" in js
    assert "if (await Auth.handleAuthRedirect())" not in js
    assert "showAppError(err)" in js
    assert 'name="viewport"' in html
    assert "/how-it-works.html" in html