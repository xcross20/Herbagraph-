from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"


def test_clinic_and_personal_portals_exist():
    clinic = (ROOT / "clinic.html").read_text(encoding="utf-8")
    me = (ROOT / "me.html").read_text(encoding="utf-8")
    assert "Clinic portal" in clinic
    assert "Personal portal" in me
    assert "Patients" in clinic
    assert "My discovery" in me
    assert "My labs" in me
    assert "HG_PORTAL = \"clinic\"" in clinic
    assert "HG_PORTAL = \"personal\"" in me
    assert "/js/workspace-app.js" in clinic
    assert "/js/workspace-app.js" in me


def test_app_html_routes_to_role_portal():
    app = (ROOT / "app.html").read_text(encoding="utf-8")
    assert "homeForCurrentSession" in app
    assert "Opening your portal" in app


def test_workspace_home_helper_maps_roles():
    js = (ROOT / "js" / "workspace-home.js").read_text(encoding="utf-8")
    assert "/clinic.html" in js
    assert "/me.html" in js
    assert "isClinicianRole" in js


def test_login_uses_portal_home():
    login = (ROOT / "login.html").read_text(encoding="utf-8")
    assert "workspace-home.js" in login
    assert "homeForCurrentSession" in login


def test_workspace_app_enforces_portal_path():
    js = (ROOT / "js" / "workspace-app.js").read_text(encoding="utf-8")
    assert "portalPath" in js
    assert "What changed" in js
    assert "renderClinicDashboard" in js
    assert "renderPersonalDashboard" in js
    assert "data-answer" in js
    assert "/api/v1/cases/" in js and "/answers" in js
    assert "Clinic portal" in js
    assert "Personal portal" in js
    assert "discovery-chat" in js
    assert "discovery-composer" in js
    assert "current_question" in js
    assert "Chat is only an interface" in js
    assert "One question per turn" in js
