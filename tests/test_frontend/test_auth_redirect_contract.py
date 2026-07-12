from pathlib import Path

_AUTH_JS = Path(__file__).resolve().parents[2] / "frontend" / "js" / "herbagraph-auth.js"
_APP_HTML = Path(__file__).resolve().parents[2] / "frontend" / "app.html"


def test_handle_auth_redirect_only_returns_true_on_callback():
    """Regression: returning true whenever a session exists broke hash navigation."""
    src = _AUTH_JS.read_text(encoding="utf-8")
    assert "const wasCallback = isAuthCallbackUrl();" in src
    assert "return wasCallback;" in src
    assert "return true;" not in src.split("async function handleAuthRedirect")[1].split("function storeLocalTokens")[0]


def test_render_returns_after_auth_callback_redirect():
    src = _APP_HTML.read_text(encoding="utf-8")
    assert "if (await Auth.handleAuthRedirect()) {" in src
    assert "return;" in src.split("if (await Auth.handleAuthRedirect())")[1].split("const hash = location.hash")[0]