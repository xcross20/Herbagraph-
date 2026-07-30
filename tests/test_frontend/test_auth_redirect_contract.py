from pathlib import Path

_AUTH_JS = Path(__file__).resolve().parents[2] / "frontend" / "js" / "herbagraph-auth.js"
_APP_HTML = Path(__file__).resolve().parents[2] / "frontend" / "app.html"


def test_handle_auth_redirect_only_returns_true_on_callback():
    """Regression: returning true whenever a session exists broke hash navigation."""
    src = _AUTH_JS.read_text(encoding="utf-8")
    assert "const wasCallback = isAuthCallbackUrl();" in src
    assert "return wasCallback;" in src
    assert "return true;" not in src.split("async function handleAuthRedirect")[1].split("function storeLocalTokens")[0]


def test_render_continues_after_auth_callback():
    """OAuth/email callbacks must fall through into session + dashboard render.

    Early-return after handleAuthRedirect() left mobile users on a gray blank page when
    hash was already #dashboard (hashchange never fired).
    """
    src = _APP_HTML.read_text(encoding="utf-8")
    assert "await Auth.handleAuthRedirect()" in src
    assert "if (await Auth.handleAuthRedirect())" not in src
    # After auth redirect, ensureSession + shell reveal still run
    assert "ensureSession()" in src
    assert 'classList.remove("hidden")' in src
    assert "showAppError" in src


def test_auth_js_routes_recovery_to_reset_password_page():
    src = _AUTH_JS.read_text(encoding="utf-8")
    assert "type=recovery" in src
    assert "/reset-password.html" in src
    assert "updatePassword" in src
