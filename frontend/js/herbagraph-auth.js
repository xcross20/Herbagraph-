/**
 * Shared auth layer: local JWT (sandbox) or Supabase Auth (production).
 */
window.HerbaGraphAuth = (function () {
  const API = window.location.origin;
  let config = null;
  let supabaseClient = null;

  async function loadConfig() {
    if (config) return config;
    const resp = await fetch(API + "/api/v1/auth/config");
    config = await resp.json();
    return config;
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
      s.onerror = reject;
      document.head.appendChild(s);
    });
    supabaseClient = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key, {
      auth: {
        detectSessionInUrl: true,
        persistSession: true,
        autoRefreshToken: true,
      },
    });
    return supabaseClient;
  }

  function isAuthCallbackUrl() {
    const hash = window.location.hash || "";
    const search = window.location.search || "";
    return (
      hash.includes("access_token=")
      || hash.includes("type=signup")
      || hash.includes("type=recovery")
      || hash.includes("type=invite")
      || search.includes("code=")
    );
  }

  /** Route Supabase email-confirm / password-reset landings to the right page. */
  function redirectAuthCallbackToApp() {
    if (!isAuthCallbackUrl()) return false;
    const hash = window.location.hash || "";
    const path = window.location.pathname;
    if (hash.includes("type=recovery")) {
      if (path.endsWith("/reset-password.html")) return false;
      window.location.replace(`/reset-password.html${window.location.search}${hash}`);
      return true;
    }
    if (
      path.endsWith("/app.html")
      || path.endsWith("/reset-password.html")
      || path.endsWith("/login.html")
      || path.endsWith("/signup.html")
    ) {
      return false;
    }
    const target = `/app.html${window.location.search}${hash || "#dashboard"}`;
    window.location.replace(target);
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
      const text = await resp.text();
      throw new Error(`Account sync failed (${resp.status}): ${text}`);
    }
    sessionStorage.removeItem("hg_signup_approval_token");
    return resp.json();
  }

  async function handleAuthRedirect() {
    const cfg = await loadConfig();
    if (cfg.auth_provider !== "supabase") return false;

    const wasCallback = isAuthCallbackUrl();
    const sb = await initSupabase();
    // detectSessionInUrl picks up tokens from email confirmation links
    const { data, error } = await sb.auth.getSession();
    if (error) throw new Error(error.message);

    if (data?.session) {
      storeSupabaseSession(data.session);
      await syncWithBackend(data.session.access_token);
      // Clean sensitive tokens from the address bar after email confirm / recovery
      if (wasCallback) {
        const isRecovery = (window.location.hash || "").includes("type=recovery");
        const cleanPath = isRecovery ? "/reset-password.html" : "/app.html#dashboard";
        window.history.replaceState({}, document.title, cleanPath);
      }
    }
    return wasCallback;
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
      const { data } = await sb.auth.getSession();
      if (data?.session) {
        storeSupabaseSession(data.session);
        await syncWithBackend(data.session.access_token);
        return true;
      }
      return false;
    }

    // Registered sessions: restore JWT pair only. Do not re-auth from stored passwords
    // (IMP-002 — passwords must not live in localStorage).
    const stored = JSON.parse(localStorage.getItem("hg_tokens") || "null");
    if (stored?.access_token && stored?.refresh_token) {
      window.hgToken = stored.access_token;
      window.hgRefreshToken = stored.refresh_token;
      return true;
    }
    // Legacy cleanup: old builds stored hg_creds with passwords
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
    // Persist tokens only — never store the password (IMP-002).
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
    const redirectTo = options.redirectTo || `${window.location.origin}${window.location.pathname}`;
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
    await signInWithGoogle({ redirectTo: `${window.location.origin}/signup.html` });
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
      const { data, error } = await sb.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: fullName || null,
            account_type: role,
          },
          emailRedirectTo: `${window.location.origin}/app.html#dashboard`,
        },
      });
      if (error) throw new Error(error.message);
      if (!data.session) {
        throw new Error("Check your email to verify your account before signing in.");
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
      await sb.auth.signOut();
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
    // Dev/demo only: ephemeral user. Password is not retained after sign-in.
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
    redirectAuthCallbackToApp,
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