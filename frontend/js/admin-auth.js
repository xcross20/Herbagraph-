/**
 * Operator console auth: master password token stored in sessionStorage.
 */
window.HerbaGraphAdminAuth = (function () {
  const STORAGE_KEY = "hg_admin_master_token";

  function getToken() {
    return sessionStorage.getItem(STORAGE_KEY);
  }

  function setToken(token) {
    sessionStorage.setItem(STORAGE_KEY, token);
  }

  function clearToken() {
    sessionStorage.removeItem(STORAGE_KEY);
  }

  function isAuthed() {
    return Boolean(getToken());
  }

  function requireAuth(redirectTo) {
    if (!isAuthed()) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `${redirectTo || "/admin/login.html"}?next=${next}`;
      return false;
    }
    return true;
  }

  async function login(password) {
    const resp = await fetch(window.location.origin + "/api/v1/admin/master-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || `Login failed (${resp.status})`);
    }
    const data = await resp.json();
    setToken(data.admin_token);
    return data;
  }

  async function api(path, options) {
    options = options || {};
    const headers = { ...(options.headers || {}) };
    const token = getToken();
    if (!token) throw new Error("Admin session expired. Sign in again.");
    headers.Authorization = `Bearer ${token}`;
    const resp = await fetch(window.location.origin + path, { ...options, headers });
    return resp;
  }

  function logout() {
    clearToken();
    window.location.href = "/admin/login.html";
  }

  return { getToken, setToken, clearToken, isAuthed, requireAuth, login, api, logout };
})();