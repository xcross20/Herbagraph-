import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"


def test_workspace_and_ask_scripts_parse():
    for name in ("workspace-app.js", "ask-app.js", "workspace-home.js", "herbagraph-auth.js"):
        path = ROOT / "js" / name
        result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, f"{name} failed to parse:\n{result.stderr}"


def test_clinic_and_personal_portals_exist():
    clinic = (ROOT / "clinic.html").read_text(encoding="utf-8")
    me = (ROOT / "me.html").read_text(encoding="utf-8")
    assert "Clinic portal" in clinic
    assert "Personal portal" in me
    assert "Patients" in clinic
    assert "Ask" in me
    assert "/ask.html" in me
    assert "/ask.html" in clinic
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
    assert "data-discovery-control" in js
    assert "data-explanation-drawer" in js
    assert "data-family-id" in js
    assert "paused concern" in js
    assert "/api/v1/cases/" in js and "/turns" in js
    assert "Clinic portal" in js
    assert "Personal portal" in js
    assert "discovery-chat" in js
    assert "discovery-composer" in js
    assert "current_question" in js
    assert "Chat is only an interface" in js
    assert "data-safety-state" in js
    assert "Urgent in-person evaluation" in js
    assert "data-select-value" in js
    assert "file_upload" in js
    assert "problem_representation" in js
    assert 'location.replace(next.pathname + next.search)' in js
    assert "/ask.html" in js
    assert "Talk to Discovery Guide" in js
    assert "Analyze my labs" in js
    assert "My investigations" in js
    assert "Recommended by Discovery" in js
    assert "/api/v1/cases/plan" in js
    assert "Longitudinal memory" in js
    assert "/api/v1/patients/" in js
    assert "longitudinal-snapshot" in js


def test_ask_portal_is_secondary_not_a_workspace_replacement():
    ask = (ROOT / "ask.html").read_text(encoding="utf-8")
    js = (ROOT / "js" / "ask-app.js").read_text(encoding="utf-8")
    assert "Discovery Guide | HerbaGraph" in ask
    assert "/js/ask-app.js" in ask
    assert "Discovery Guide" in js
    assert "Start wherever makes sense" in js
    assert "/api/v1/cases" in js
    assert "ask-rail" in js
    assert "Back to workspace" in js
    assert "Literature" in js
    assert "/documents" in js
    assert "why? show evidence" in js
    assert "pubmed.ncbi.nlm.nih.gov" in js
    assert "data-pending-prompt" in js
    assert "data-ask-thinking" in js
    assert "Discovery Guide is thinking" in js
    assert "/api/v1/cases/stream" in js
    assert "/turns/stream" in js
    assert "hg_active_patient_id" in js
    assert "Discovery is paused" in js
    assert "data-ask-control" in js
    assert "data-explanation-drawer" in js
    assert "data-family-id" in js
    assert "Prepare for clinician" in js
    assert "claim_cards" in js
    assert "Missing literature stays a limitation" in js
    assert "data-evidence-id" in js
    assert "Paused:" in js
    assert "Response mode:" in js
    assert "Last time" in js
    assert "Why is this here" in js
    assert "/findings/" in js
    assert "SpeechRecognition" in js
    assert "ask.html?patient=" in (ROOT / "js" / "workspace-app.js").read_text(encoding="utf-8")
    assert 'e.key === "Enter"' in js
