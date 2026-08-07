/**
 * Shared auth layer: local JWT (sandbox) or Supabase Auth (production).
 *
 * Email confirmation / OAuth / password-reset land on /auth/callback.html
 * (or recovery on /reset-password.html). Never put tokens behind a second
 * hash fragment like app.html#dashboard — Supabase needs a clean redirect URL.
 */
window.HerbaGraphAuth = (function () {
  const API = window.location.origin;
  const AUTH_CALLBACK_PATH = "/auth/callback.html";
  let config = null;
  let supabaseClient = null;

  async function loadConfig() {
    if (config) return config;
    const resp = await fetch(API + "/api/v1/auth/config");
    config = await resp.json();
    return config;
  }

  function authCallbackUrl() {
    return `${window.location.origin}${AUTH_CALLBACK_PATH}`;
  }

  async function initSupabase() {
    const cfg = await loadConfig();
    if (cfg.auth_provider !== "supabase" || !cfg.supabase_url || !cfg.supabase_anon_key) {
      return null;
    }
    if (supabaseClient) return supabaseClient;
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js";
      s.onload = resolve;
      s.onerror = () => reject(new Error("Could not load Supabase client library."));
      document.head.appendChild(s);
    });
    if (!window.supabase || !window.supabase.createClient) {
      throw new Error("Supabase client library failed to initialize.");
    }
    supabaseClient = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key, {
      auth: {
        // PKCE is the default for browser clients; keeps email/OAuth links exchangeable.
        flowType: "pkce",
        detectSessionInUrl: true,
        persistSession: true,
        autoRefreshToken: true,
      },
    });
    return supabaseClient;
  }

  function _hashParams() {
    const raw = (window.location.hash || "").replace(/^#/, "");
    return new URLSearchParams(raw);
  }

  function _queryParams() {
    return new URLSearchParams(window.location.search || "");
  }

  function isAuthCallbackUrl() {
    const hash = window.location.hash || "";
    const search = window.location.search || "";
    return (
      hash.includes("access_token=")
      || hash.includes("refresh_token=")
      || hash.includes("type=signup")
      || hash.includes("type=recovery")
      || hash.includes("type=invite")
      || hash.includes("type=magiclink")
      || hash.includes("type=email")
      || search.includes("code=")
      || search.includes("error=")
      || search.includes("error_description=")
      || hash.includes("error=")
    );
  }

  function readAuthErrorFromUrl() {
    const q = _queryParams();
    const h = _hashParams();
    const error = q.get("error") || h.get("error");
    if (!error) return null;
    const desc = q.get("error_description") || h.get("error_description") || error;
    try {
      return decodeURIComponent(String(desc).replace(/\+/g, " "));
    } catch (_) {
      return String(desc).replace(/\+/g, " ");
    }
  }

  /**
   * Route Supabase email-confirm / OAuth landings to the dedicated callback page.
   * Recovery links stay on / go to reset-password.html.
   */
  function redirectAuthCallbackToApp() {
    if (!isAuthCallbackUrl()) return false;
    const hash = window.location.hash || "";
    const path = window.location.pathname || "";
    const search = window.location.search || "";

    // Already on a page that will process the session.
    if (
      path.endsWith("/auth/callback.html")
      || path.endsWith("/reset-password.html")
      || path.includes("/auth/callback")
    ) {
      return false;
    }

    // Password recovery → dedicated reset page (keep tokens in hash/query).
    if (hash.includes("type=recovery") || search.includes("type=recovery")) {
      if (path.endsWith("/reset-password.html")) return false;
      window.location.replace(`/reset-password.html${search}${hash}`);
      return true;
    }

    // Signup confirm / magic link / OAuth → clean callback (no #dashboard clash).
    window.location.replace(`${AUTH_CALLBACK_PATH}${search}${hash}`);
    return true;
  }

  async function syncWithBackend(accessToken) {
    const headers = { Authorization: `Bearer ${accessToken}` };
    const approvalToken = sessionStorage.getItem("hg_signup_approval_token");
    if (approvalToken) headers["X-Signup-Approval-Token"] = approvalToken;
    const resp = await fetch(API + "/api/v1/auth/sync", {
      method: "POST",
      headers,
    });
    if (!resp.ok) {
      let detail = await resp.text();
      try {
        const j = JSON.parse(detail);
        detail = j.detail || detail;
      } catch (_) { /* raw */ }
      throw new Error(typeof detail === "string" ? detail : `Account sync failed (${resp.status})`);
    }
    sessionStorage.removeItem("hg_signup_approval_token");
    return resp.json();
  }

  /**
   * Exchange URL tokens/code for a Supabase session and sync the HerbaGraph user.
   * Used by /auth/callback.html and optionally by other pages.
   */
  async function completeAuthCallback(options) {
    options = options || {};
    const successPath = options.successPath || "/app.html#dashboard";
    const onboardPath = options.onboardPath || "/app.html?onboard=1#dashboard";

    const cfg = await loadConfig();
    if (cfg.auth_provider !== "supabase") {
      return { ok: false, needsLogin: true, message: "Supabase Auth is not enabled." };
    }

    const urlError = readAuthErrorFromUrl();
    if (urlError) {
      return { ok: false, needsLogin: true, message: urlError };
    }

    const sb = await initSupabase();
    if (!sb) {
      return {
        ok: false,
        needsLogin: true,
        message: "Supabase is not configured (missing URL or anon key).",
      };
    }

    // Explicit PKCE code exchange (email confirm / OAuth with ?code=).
    const code = _queryParams().get("code");
    if (code) {
      const { data: exData, error: exErr } = await sb.auth.exchangeCodeForSession(code);
      if (exErr) {
        return {
          ok: false,
          needsLogin: true,
          message: exErr.message || "Could not exchange confirmation code. The link may have expired.",
        };
      }
      if (exData?.session) {
        storeSupabaseSession(exData.session);
        try {
          await syncWithBackend(exData.session.access_token);
        } catch (syncErr) {
          return {
            ok: false,
            needsLogin: true,
            message: syncErr.message || "Account sync failed after confirmation.",
          };
        }
        const onboard = localStorage.getItem("hg_onboarding_pending") === "1";
        return { ok: true, redirectTo: onboard ? onboardPath : successPath };
      }
    }

    // Implicit / hash tokens — detectSessionInUrl should parse these on client create.
    // Also try getSession after a brief tick for race with internal parser.
    let session = null;
    {
      const { data, error } = await sb.auth.getSession();
      if (error) {
        return { ok: false, needsLogin: true, message: error.message };
      }
      session = data?.session || null;
    }

    if (!session && isAuthCallbackUrl()) {
      // One more attempt: setSession from hash access_token if present.
      const h = _hashParams();
      const accessToken = h.get("access_token");
      const refreshToken = h.get("refresh_token");
      if (accessToken && refreshToken) {
        const { data, error } = await sb.auth.setSession({
          access_token: accessToken,
          refresh_token: refreshToken,
        });
        if (error) {
          return { ok: false, needsLogin: true, message: error.message };
        }
        session = data?.session || null;
      }
    }

    if (!session) {
      return {
        ok: false,
        needsLogin: true,
        message:
          "No active session found from this link. It may have already been used or expired. Sign in with your email and password.",
      };
    }

    storeSupabaseSession(session);
    try {
      await syncWithBackend(session.access_token);
    } catch (syncErr) {
      return {
        ok: false,
        needsLogin: true,
        message: syncErr.message || "Account sync failed after confirmation.",
      };
    }

    const isRecovery =
      (window.location.hash || "").includes("type=recovery")
      || _queryParams().get("type") === "recovery";
    if (isRecovery) {
      return { ok: true, redirectTo: "/reset-password.html" };
    }

    const onboard = localStorage.getItem("hg_onboarding_pending") === "1";
    return { ok: true, redirectTo: onboard ? onboardPath : successPath };
  }

  async function handleAuthRedirect() {
    const cfg = await loadConfig();
    if (cfg.auth_provider !== "supabase") return false;

    if (!isAuthCallbackUrl()) return false;

    // Recovery should be handled on reset-password page only.
    const isRecovery =
      (window.location.hash || "").includes("type=recovery")
      || _queryParams().get("type") === "recovery";
    if (isRecovery && !(window.location.pathname || "").endsWith("/reset-password.html")) {
      return false;
    }

    const result = await completeAuthCallback();
    if (result.ok) {
      const clean = result.redirectTo || "/app.html#dashboard";
      window.history.replaceState({}, document.title, clean.split("#")[0] || clean);
      if (clean.includes("#") || clean.includes("?")) {
        // Let callers navigate if needed; still return true so they can redirect.
      }
      // If still on callback-like page, caller will navigate; if on app.html, clean tokens.
      if ((window.location.pathname || "").endsWith("/app.html")) {
        window.history.replaceState({}, document.title, clean);
      }
      return true;
    }
    if (result.message) {
      throw new Error(result.message);
    }
    return true;
  }

  function storeLocalTokens(tokens) {
    window.hgToken = tokens.access_token;
    window.hgRefreshToken = tokens.refresh_token;
    localStorage.setItem("hg_tokens", JSON.stringify(tokens));
  }

  function storeSupabaseSession(session) {
    window.hgToken = session.access_token;
    window.hgRefreshToken = session.refresh_token;
    localStorage.setItem("hg_tokens", JSON.stringify({
      access_token: session.access_token,
      refresh_token: session.refresh_token,
    }));
    localStorage.setItem("hg_auth_provider", "supabase");
  }

  async function ensureSession() {
    const cfg = await loadConfig();

    if (cfg.auth_provider === "supabase") {
      const sb = await initSupabase();
      if (!sb) return false;
      const { data } = await sb.auth.getSession();
      if (data?.session) {
        storeSupabaseSession(data.session);
        await syncWithBackend(data.session.access_token);
        return true;
      }
      return false;
    }

    const stored = JSON.parse(localStorage.getItem("hg_tokens") || "null");
    if (stored?.access_token && stored?.refresh_token) {
      window.hgToken = stored.access_token;
      window.hgRefreshToken = stored.refresh_token;
      return true;
    }
    try {
      localStorage.removeItem("hg_creds");
    } catch (_) { /* ignore */ }
    return false;
  }

  async function refreshTokens() {
    const cfg = await loadConfig();
    if (cfg.auth_provider === "supabase") {
      const sb = await initSupabase();
      const { data, error } = await sb.auth.refreshSession();
      if (error || !data?.session) throw new Error("Session expired");
      storeSupabaseSession(data.session);
      return;
    }
    const resp = await fetch(API + "/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: window.hgRefreshToken }),
    });
    if (!resp.ok) throw new Error("Session expired");
    storeLocalTokens(await resp.json());
  }

  async function signInWithPassword(email, password) {
    const cfg = await loadConfig();
    if (cfg.auth_provider === "supabase") {
      const sb = await initSupabase();
      const { data, error } = await sb.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message);
      storeSupabaseSession(data.session);
      await syncWithBackend(data.session.access_token);
      return;
    }
    try {
      localStorage.removeItem("hg_creds");
    } catch (_) { /* ignore */ }
    localStorage.removeItem("hg_tokens");
    const resp = await fetch(API + "/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    storeLocalTokens(await resp.json());
    localStorage.setItem("hg_auth_provider", "local");
  }

  async function verifyAccessCodeForOAuth(accessCode) {
    const resp = await fetch(API + "/api/v1/auth/verify-access-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_code: accessCode }),
    });
    if (!resp.ok) {
      let detail = await resp.text();
      try {
        const j = JSON.parse(detail);
        detail = j.detail || detail;
      } catch (_) { /* raw */ }
      throw new Error(detail);
    }
    const body = await resp.json();
    return body.approval_token;
  }

  async function signInWithGoogle(options) {
    options = options || {};
    const cfg = await loadConfig();
    if (!cfg.google_oauth_enabled) {
      throw new Error("Google sign-in is not enabled.");
    }
    const sb = await initSupabase();
    if (!sb) throw new Error("Supabase Auth is not configured.");
    // Always land on the dedicated callback so PKCE/code exchange is reliable.
    const redirectTo = options.redirectTo || authCallbackUrl();
    const { error } = await sb.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo,
        queryParams: { prompt: "select_account" },
      },
    });
    if (error) throw new Error(error.message);
  }

  async function startGoogleSignup(accessCode, role) {
    const cfg = await loadConfig();
    if (cfg.signup_access_required) {
      if (!accessCode || !String(accessCode).trim()) {
        throw new Error("Access code is required before continuing with Google.");
      }
      const token = await verifyAccessCodeForOAuth(String(accessCode).trim());
      sessionStorage.setItem("hg_signup_approval_token", token);
    }
    sessionStorage.setItem("hg_account_type", role === "clinician" ? "clinician" : "individual");
    sessionStorage.setItem("hg_oauth_mode", "signup");
    localStorage.setItem("hg_onboarding_pending", "1");
    await signInWithGoogle({ redirectTo: authCallbackUrl() });
  }

  async function verifySignupAccess(email, accessCode) {
    const resp = await fetch(API + "/api/v1/auth/verify-signup-access", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, access_code: accessCode }),
    });
    if (!resp.ok) {
      let detail = await resp.text();
      try {
        const j = JSON.parse(detail);
        detail = j.detail || detail;
      } catch (_) { /* raw */ }
      throw new Error(detail);
    }
  }

  async function signUp(email, password, fullName, accessCode, options) {
    options = options || {};
    const role = options.role === "clinician" ? "clinician" : "individual";
    const cfg = await loadConfig();
    if (cfg.signup_access_required) {
      if (!accessCode || !String(accessCode).trim()) {
        throw new Error("Access code is required.");
      }
      await verifySignupAccess(email, String(accessCode).trim());
    }
    if (cfg.auth_provider === "supabase") {
      const sb = await initSupabase();
      // Clean URL — no #dashboard (breaks Supabase token hash / allowlist).
      const emailRedirectTo = authCallbackUrl();
      const { data, error } = await sb.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: fullName || null,
            account_type: role,
            // Survives email confirmation so /auth/sync can admit private-preview users
            // without relying on in-memory approval that expires or is worker-local.
            hg_signup_gate: cfg.signup_access_required ? "ok" : "open",
          },
          emailRedirectTo,
        },
      });
      if (error) throw new Error(error.message);
      if (!data.session) {
        // Email confirmation required — not an error.
        const err = new Error(
          "Check your email to verify your account. Open the confirmation link to finish signing up."
        );
        err.code = "EMAIL_CONFIRMATION_REQUIRED";
        throw err;
      }
      storeSupabaseSession(data.session);
      await syncWithBackend(data.session.access_token);
      return;
    }
    const resp = await fetch(API + "/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        full_name: fullName || null,
        access_code: accessCode || null,
        role,
      }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    await signInWithPassword(email, password);
  }

  async function resetPassword(email) {
    const cfg = await loadConfig();
    if (cfg.auth_provider !== "supabase") {
      throw new Error("Password reset is managed via Supabase when AUTH_PROVIDER=supabase.");
    }
    const sb = await initSupabase();
    // Reset page can parse recovery tokens; keep that dedicated path.
    const redirectTo = `${window.location.origin}/reset-password.html`;
    const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo });
    if (error) throw new Error(error.message);
  }

  async function updatePassword(newPassword) {
    const cfg = await loadConfig();
    if (cfg.auth_provider !== "supabase") {
      throw new Error("Password updates are managed via Supabase when AUTH_PROVIDER=supabase.");
    }
    const sb = await initSupabase();
    const { error } = await sb.auth.updateUser({ password: newPassword });
    if (error) throw new Error(error.message);
  }

  async function signOut() {
    const cfg = await loadConfig();
    if (cfg.auth_provider === "supabase") {
      const sb = await initSupabase();
      if (sb) await sb.auth.signOut();
    }
    localStorage.removeItem("hg_tokens");
    localStorage.removeItem("hg_creds");
    localStorage.removeItem("hg_auth_provider");
    window.hgToken = null;
    window.hgRefreshToken = null;
  }

  async function continueAsGuest() {
    const cfg = await loadConfig();
    if (!cfg.allow_guest_auth) {
      throw new Error("Guest access is disabled. Create an account or sign in to keep your labs and reports.");
    }
    const email = `guest-${crypto.randomUUID()}@guest.herbagraph-app.io`;
    const password = `Guest${Math.random().toString(36).slice(2)}A1!`;
    localStorage.removeItem("hg_tokens");
    try {
      localStorage.removeItem("hg_creds");
    } catch (_) { /* ignore */ }
    const resp = await fetch(API + "/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: "Guest" }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    await signInWithPassword(email, password);
  }

  async function api(path, options) {
    options = options || {};
    const headers = { ...(options.headers || {}) };
    if (!headers.Authorization && window.hgToken) {
      headers.Authorization = `Bearer ${window.hgToken}`;
    }
    let resp = await fetch(API + path, { ...options, headers });
    if (resp.status === 401 && window.hgRefreshToken) {
      await refreshTokens();
      headers.Authorization = `Bearer ${window.hgToken}`;
      resp = await fetch(API + path, { ...options, headers });
    }
    return resp;
  }

  return {
    loadConfig,
    authCallbackUrl,
    redirectAuthCallbackToApp,
    completeAuthCallback,
    handleAuthRedirect,
    ensureSession,
    refreshTokens,
    signInWithPassword,
    signInWithGoogle,
    startGoogleSignup,
    verifyAccessCodeForOAuth,
    signUp,
    resetPassword,
    updatePassword,
    signOut,
    continueAsGuest,
    api,
    isSupabase: async () => (await loadConfig()).auth_provider === "supabase",
  };
})();

// If email confirmation or recovery lands on a public page, forward immediately.
window.__hgAuthRedirecting = window.HerbaGraphAuth.redirectAuthCallbackToApp();
