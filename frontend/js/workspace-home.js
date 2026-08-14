/**
 * Portal homes: clinician vs personal. One shared API, two front doors.
 */
window.HerbaGraphWorkspace = (function () {
  const CLINICIAN_ROLES = new Set(["clinician", "organization_admin", "admin"]);

  function isClinicianRole(role) {
    return CLINICIAN_ROLES.has(String(role || "").toLowerCase());
  }

  function portalPath(role) {
    return isClinicianRole(role) ? "/clinic.html" : "/me.html";
  }

  function workspaceHome(role, options) {
    options = options || {};
    const hash = options.hash || "#dashboard";
    const query = options.onboard ? "?onboard=1" : (options.query || "");
    return `${portalPath(role)}${query}${hash.startsWith("#") ? hash : `#${hash}`}`;
  }

  async function homeForCurrentSession(options) {
    const Auth = window.HerbaGraphAuth;
    if (!Auth) return "/login.html";
    if (!(await Auth.ensureSession())) return "/login.html";
    const resp = await fetch(`${window.location.origin}/api/v1/auth/me`, {
      headers: window.hgToken ? { Authorization: `Bearer ${window.hgToken}` } : {},
    });
    if (!resp.ok) return "/login.html";
    const me = await resp.json();
    return workspaceHome(me.role, options);
  }

  return { isClinicianRole, portalPath, workspaceHome, homeForCurrentSession };
})();
