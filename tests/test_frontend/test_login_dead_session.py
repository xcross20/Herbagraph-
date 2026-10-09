"""A dead saved session must not reload the sign-in page."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_JS = (ROOT / "frontend" / "js" / "herbagraph-auth.js").read_text(encoding="utf-8")
HOME_JS = (ROOT / "frontend" / "js" / "workspace-home.js").read_text(encoding="utf-8")
LOGIN = (ROOT / "frontend" / "login.html").read_text(encoding="utf-8")


def test_local_ensure_session_checks_the_token_and_can_refresh():
    block = AUTH_JS.split("function clearStoredSession")[1].split("async function refreshTokens")[0]
    ensure = block.split("async function ensureSession")[1]
    assert "/api/v1/auth/me" in block
    assert "localAccessAccepted()" in ensure
    assert "refreshTokens()" in ensure
    assert "discardDeadLocalSession()" in ensure


def test_dead_local_session_is_cleared_instead_of_kept():
    assert "hg_session_expired" in AUTH_JS
    assert "localStorage.removeItem(\"hg_tokens\")" in AUTH_JS
    discard = AUTH_JS.split("function discardDeadLocalSession")[1].split("async function ensureSession")[0]
    assert "clearStoredSession" in discard


def test_workspace_home_drops_dead_tokens_before_sending_user_to_login():
    home = HOME_JS.split("async function homeForCurrentSession")[1].split("function familyDialogHtml")[0]
    assert "signOut()" in home
    assert 'return "/login.html"' in home


def test_login_page_does_not_navigate_to_itself():
    assert 'if (!dest || dest.startsWith("/login")) return false;' in LOGIN
    guarded = 'if (nextUrl && !nextUrl.includes("/app.html") && nextUrl.startsWith("/"))'
    assert LOGIN.count("location.href = nextUrl;") == LOGIN.count(guarded)
