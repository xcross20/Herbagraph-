"""IMP-002 frontend contracts: no auto-guest; no password in localStorage helpers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_JS = (ROOT / "frontend" / "js" / "herbagraph-auth.js").read_text(encoding="utf-8")
LOGIN = (ROOT / "frontend" / "login.html").read_text(encoding="utf-8")
REPORT = (ROOT / "frontend" / "report.html").read_text(encoding="utf-8")


def test_local_login_does_not_persist_password_in_localstorage():
    # After sign-in, hg_creds must be removed / not written with password
    assert 'localStorage.removeItem("hg_creds")' in AUTH_JS
    assert "localStorage.setItem(\"hg_creds\", JSON.stringify({ email, password }))" not in AUTH_JS


def test_ensure_session_uses_tokens_only_for_local():
    assert "hg_tokens" in AUTH_JS
    # Must not re-login via stored password in ensureSession
    ensure = AUTH_JS.split("async function ensureSession")[1].split("async function refreshTokens")[0]
    assert "auth/login" not in ensure
    assert "hg_creds" not in ensure or "removeItem" in ensure


def test_report_never_auto_creates_guest():
    assert "continueAsGuest" not in REPORT or "Sign in required" in REPORT
    # Explicit: no await Auth.continueAsGuest in report ensureAuth
    ensure = REPORT.split("async function ensureAuth")[1].split("function humanizeError")[0]
    assert "continueAsGuest" not in ensure


def test_login_emphasizes_registered_account():
    assert "Create a registered account" in LOGIN or "signup.html" in LOGIN
    assert "Registered sessions" in LOGIN or "persist" in LOGIN.lower()


def test_login_offers_supabase_magic_link():
    assert "Email me a sign-in link" in LOGIN
    assert 'id="magic-link-btn"' in LOGIN
    assert "requestMagicLink" in AUTH_JS
    assert "signInWithOtp" in AUTH_JS
    assert "shouldCreateUser: false" in AUTH_JS
    assert "emailRedirectTo: authCallbackUrl()" in AUTH_JS
