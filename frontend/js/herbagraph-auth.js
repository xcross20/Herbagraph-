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

  /** Send Supabase email-confirm / password-reset landings to the app shell. */
  function redirectAuthCallbackToApp() {
    if (!isAuthCallbackUrl()) return false;
    if (window.location.pathname.endsWith("/app.html")) return false;
    const target = `/app.html${window.location.search}${window.location.hash || "#dashboard"}`;
    window.location.replace(target);
    return true;
  }

  async function handleAuthRedirect() {
    const cfg = await loadConfig();
    if (cfg.auth_provider !== "supabase") return false;

    const sb = await initSupabase();
    // detectSessionInUrl picks up tokens from email confirmation links
    const { data, error } = await sb.auth.getSession();
    if (error) throw new Error(error.message);

    if (data?.session) {
      storeSupabaseSession(data.session);
      await fetch(API + "/api/v1/auth/sync", {
        method: "POST",
        headers: { Authorization: `Bearer ${data.session.access_token}` },
      });
      // Clean sensitive tokens from the address bar
      if (isAuthCallbackUrl()) {
        window.history.replaceState({}, document.title, "/app.html#dashboard");
      }
      return true;
    }
    return false;
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
        await fetch(API + "/api/v1/auth/sync", {
          method: "POST",
          headers: { Authorization: `Bearer ${data.session.access_token}` },
        });
        return true;
      }
      return false;
    }

    const creds = JSON.parse(localStorage.getItem("hg_creds") || "null");
    if (!creds) return false;

    const stored = JSON.parse(localStorage.getItem("hg_tokens") || "null");
    if (stored?.access_token && stored?.refresh_token) {
      window.hgToken = stored.access_token;
      window.hgRefreshToken = stored.refresh_token;
      return true;
    }

    const login = await fetch(API + "/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(creds),
    });
    if (!login.ok) return false;
    const tokens = await login.json();
    storeLocalTokens(tokens);
    return true;
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
      await fetch(API + "/api/v1/auth/sync", {
        method: "POST",
        headers: { Authorization: `Bearer ${data.session.access_token}` },
      });
      return;
    }
    localStorage.setItem("hg_creds", JSON.stringify({ email, password }));
    localStorage.removeItem("hg_tokens");
    const resp = await fetch(API + "/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    storeLocalTokens(await resp.json());
  }

  async function signUp(email, password, fullName) {
    const cfg = await loadConfig();
    if (cfg.auth_provider === "supabase") {
      const sb = await initSupabase();
      const { data, error } = await sb.auth.signUp({
        email,
        password,
        options: {
          data: { full_name: fullName || null },
          emailRedirectTo: `${window.location.origin}/app.html`,
        },
      });
      if (error) throw new Error(error.message);
      if (!data.session) {
        throw new Error("Check your email to verify your account before signing in.");
      }
      storeSupabaseSession(data.session);
      await fetch(API + "/api/v1/auth/sync", {
        method: "POST",
        headers: { Authorization: `Bearer ${data.session.access_token}` },
      });
      return;
    }
    const resp = await fetch(API + "/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: fullName || null }),
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
    const redirectTo = `${window.location.origin}/app.html`;
    const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo });
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
      throw new Error("Guest access is disabled. Create an account to continue.");
    }
    const email = `guest-${crypto.randomUUID()}@guest.herbagraph-app.io`;
    const password = `Guest${Math.random().toString(36).slice(2)}A1`;
    localStorage.setItem("hg_creds", JSON.stringify({ email, password }));
    localStorage.removeItem("hg_tokens");
    const resp = await fetch(API + "/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: "Guest" }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    await signInWithPassword(email, password);
  }

  return {
    loadConfig,
    redirectAuthCallbackToApp,
    handleAuthRedirect,
    ensureSession,
    refreshTokens,
    signInWithPassword,
    signUp,
    resetPassword,
    signOut,
    continueAsGuest,
    isSupabase: async () => (await loadConfig()).auth_provider === "supabase",
  };
})();

// If email confirmation lands on / or /index.html, forward to the app shell immediately.
window.__hgAuthRedirecting = window.HerbaGraphAuth.redirectAuthCallbackToApp();