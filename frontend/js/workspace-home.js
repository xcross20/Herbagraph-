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

  function familyDialogHtml(family) {
    const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    const facts = (family.supporting_facts || []).slice(0, 8).map((item) =>
      `<li>${esc(item.name)}: ${esc(item.value)} <span class="muted">${esc(item.provenance || "")}</span></li>`
    ).join("");
    const unknowns = (family.unknowns || []).slice(0, 8).map((item) => `<li>${esc(item)}</li>`).join("");
    const evals = (family.evaluations || []).map((item) =>
      `<li><strong>${esc(item.label)}</strong><p class="muted">${esc(item.coverage_relation || "")}. ${esc(item.can_tell || "")}</p><p class="muted">Cannot tell: ${esc(item.cannot_tell || "")}</p></li>`
    ).join("");
    const cards = (family.claim_card_ids || []).map((id) => `<li>${esc(id)}</li>`).join("");
    return `
      <div class="hg-why-dialog" role="dialog" aria-modal="true" aria-labelledby="hg-why-title">
        <header class="hg-why-head">
          <div>
            <p class="hg-why-kicker">Why is this here?</p>
            <h2 id="hg-why-title">${esc(family.label || "Investigation family")}</h2>
          </div>
          <button type="button" class="hg-why-close" data-why-close aria-label="Close">Close</button>
        </header>
        <div class="hg-why-body">
          <section>
            <h3>Why it is being considered</h3>
            <ul>${facts || '<li class="muted">Related findings are present. This is not a diagnosis.</li>'}</ul>
          </section>
          <section>
            <h3>What does not fit / remains unknown</h3>
            <ul>${unknowns || '<li class="muted">No contradictions recorded yet.</li>'}</ul>
          </section>
          <section>
            <h3>How the biology may connect</h3>
            <p>${esc(family.rationale || "Open because related findings are present. Coverage is completeness, not probability.")}</p>
            <p class="muted">Relationship: ${esc(family.relationship || "contributor_evaluation")}. Not a diagnosis.</p>
          </section>
          <section>
            <h3>Ways to evaluate</h3>
            <ul>${evals || '<li class="muted">No ranked options yet.</li>'}</ul>
          </section>
          <section>
            <h3>Research</h3>
            <ul>${cards || '<li class="muted">No stored citation supports this statement. Missing literature stays a limitation.</li>'}</ul>
          </section>
          <section>
            <h3>Next action</h3>
            <p>${esc(family.next_action || "Prepare for clinician")}</p>
          </section>
        </div>
      </div>`;
  }

  function openFamilyDialog(family) {
    if (!family) return;
    closeFamilyDialog();
    const overlay = document.createElement("div");
    overlay.className = "hg-why-overlay";
    overlay.setAttribute("data-why-overlay", "1");
    overlay.innerHTML = familyDialogHtml(family);
    document.body.appendChild(overlay);
    const closeBtn = overlay.querySelector("[data-why-close]");
    const onKey = (event) => {
      if (event.key === "Escape") closeFamilyDialog();
    };
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeFamilyDialog();
    });
    if (closeBtn) closeBtn.onclick = closeFamilyDialog;
    document.addEventListener("keydown", onKey);
    overlay._onKey = onKey;
    if (closeBtn) closeBtn.focus();
  }

  function closeFamilyDialog() {
    const overlay = document.querySelector("[data-why-overlay]");
    if (!overlay) return;
    if (overlay._onKey) document.removeEventListener("keydown", overlay._onKey);
    overlay.remove();
  }

  return { isClinicianRole, portalPath, workspaceHome, homeForCurrentSession, openFamilyDialog, closeFamilyDialog };
})();
