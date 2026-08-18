/* Shared workspace application. Loaded by clinic.html and me.html. */
window.HG_PORTAL = window.HG_PORTAL || "personal";
window.HG_PORTAL_HOME = window.HG_PORTAL === "clinic" ? "/clinic.html" : "/me.html";

document.getElementById("app-nav-logo").innerHTML = herbagraphLogoLink((window.HG_PORTAL_HOME || "/me.html") + "#dashboard");
const mobileBrand = document.getElementById("mobile-topbar-brand");
if (mobileBrand) mobileBrand.innerHTML = herbagraphLogoLink((window.HG_PORTAL_HOME || "/me.html") + "#dashboard");
const API = window.location.origin;
const Auth = window.HerbaGraphAuth;
let currentUser = null;
let lastDashboard = null;

function isMobileNav() {
  return window.matchMedia("(max-width: 900px)").matches;
}

function setSidebarOpen(open) {
  const shell = document.getElementById("app-shell");
  const sidebar = document.getElementById("app-sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");
  const toggle = document.getElementById("mobile-nav-toggle");
  if (!sidebar) return;
  const shouldOpen = Boolean(open) && isMobileNav();
  sidebar.classList.toggle("is-open", shouldOpen);
  shell?.classList.toggle("sidebar-open", shouldOpen);
  if (backdrop) {
    // Class-based visibility — more reliable than [hidden] vs display:block on iOS Safari
    backdrop.classList.toggle("is-visible", shouldOpen);
    backdrop.hidden = !shouldOpen;
    backdrop.setAttribute("aria-hidden", shouldOpen ? "false" : "true");
  }
  if (toggle) {
    toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    toggle.setAttribute("aria-label", shouldOpen ? "Close menu" : "Open menu");
  }
  document.body.classList.toggle("nav-locked", shouldOpen);
}

function closeSidebar() {
  setSidebarOpen(false);
}

function openSidebar() {
  setSidebarOpen(true);
}

function toggleSidebar() {
  const sidebar = document.getElementById("app-sidebar");
  setSidebarOpen(!sidebar?.classList.contains("is-open"));
}

function wireMobileNav() {
  if (window.__hgMobileNavWired) {
    closeSidebar();
    return;
  }
  window.__hgMobileNavWired = true;

  const toggle = document.getElementById("mobile-nav-toggle");
  const closeBtn = document.getElementById("sidebar-close");
  const backdrop = document.getElementById("sidebar-backdrop");
  if (toggle) {
    toggle.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleSidebar();
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      closeSidebar();
    });
  }
  if (backdrop) {
    backdrop.addEventListener("click", closeSidebar);
  }
  document.querySelectorAll(".sidebar-link").forEach((link) => {
    link.addEventListener("click", () => {
      if (isMobileNav()) closeSidebar();
    });
  });
  window.addEventListener("resize", () => {
    if (!isMobileNav()) closeSidebar();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSidebar();
  });
  closeSidebar();
}

function showAppError(err) {
  // Keep shell visible so the error is not hidden with the chrome (was a pure gray screen).
  const shell = document.getElementById("app-shell");
  shell?.classList.remove("hidden");
  closeSidebar();
  document.body.classList.remove("nav-locked");
  const main = document.getElementById("app-main");
  if (!main) return;
  main.innerHTML = `
    <div class="app-card app-error-card" style="max-width:480px;margin:1.5rem auto">
      <h2 style="margin:0 0 0.5rem">Something went wrong</h2>
      <p class="error">${esc(err?.message || err || "Unknown error")}</p>
      <div class="page-header-actions" style="margin-top:1rem">
        <button type="button" class="app-btn app-btn-primary" id="error-retry-btn">Try again</button>
        <a class="app-btn" href="/login.html">Back to sign in</a>
      </div>
    </div>`;
  document.getElementById("error-retry-btn")?.addEventListener("click", () => {
    location.reload();
  });
}

const ICON_GRID = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>';

async function api(path, method = "GET", body) {
  const headers = { "Content-Type": "application/json" };
  if (window.hgToken) headers.Authorization = `Bearer ${window.hgToken}`;
  let resp = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (resp.status === 401 && window.hgRefreshToken) {
    await Auth.refreshTokens();
    headers.Authorization = `Bearer ${window.hgToken}`;
    resp = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  }
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(friendlyApiError(method, path, resp.status, text));
  }
  if (resp.status === 204) return null;
  return resp.json();
}

/** Download original patient-uploaded lab file (encrypted at rest; decrypted for owner only). */
async function downloadLabUpload(labReportId, suggestedName) {
  const headers = {};
  if (window.hgToken) headers.Authorization = `Bearer ${window.hgToken}`;
  let resp = await fetch(API + `/api/v1/labs/${labReportId}/download`, { headers });
  if (resp.status === 401 && window.hgRefreshToken) {
    await Auth.refreshTokens();
    headers.Authorization = `Bearer ${window.hgToken}`;
    resp = await fetch(API + `/api/v1/labs/${labReportId}/download`, { headers });
  }
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(friendlyApiError("GET", `/api/v1/labs/${labReportId}/download`, resp.status, text));
  }
  const blob = await resp.blob();
  let filename = suggestedName || "lab-upload";
  const cd = resp.headers.get("Content-Disposition") || "";
  const m = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i.exec(cd);
  if (m) {
    try {
      filename = decodeURIComponent(m[1] || m[2] || filename);
    } catch (_) {
      filename = m[2] || filename;
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

window.downloadLabUpload = downloadLabUpload;

function friendlyApiError(method, path, status, text) {
  let detail = text;
  try {
    const j = JSON.parse(text);
    detail = j.detail || text;
  } catch { /* raw */ }
  if (path.includes("/auth/me") && (status === 500 || status === 503)) {
    return "The server could not reach the database after sign-in. Set DATABASE_URL on Railway. Diagnostic: " + detail;
  }
  return `${method} ${path} (${status}): ${detail}`;
}

async function ensureSession() {
  if (!(await Auth.ensureSession())) return false;
  currentUser = await api("/api/v1/auth/me");
  applyWorkspaceChrome();
  return true;
}

function isClinicianWorkspace() {
  const role = String((currentUser && currentUser.role) || "").toLowerCase();
  return role === "clinician" || role === "organization_admin" || role === "admin";
}

function applyWorkspaceChrome() {
  const clinician = isClinicianWorkspace();
  document.body.dataset.workspace = clinician ? "clinician" : "consumer";
  const patientsLabel = document.getElementById("nav-patients-label");
  if (patientsLabel) patientsLabel.textContent = clinician ? "Patients" : "My profile";
}

function rememberPatientId(patientId) {
  if (patientId) sessionStorage.setItem("hg_active_patient_id", patientId);
  else sessionStorage.removeItem("hg_active_patient_id");
}

async function resolveActivePatientId(explicitId) {
  const patients = await ensurePatients();
  if (!patients.length) return { patientId: null, patients };
  if (!isClinicianWorkspace()) {
    const self = patients.find((p) => String(p.display_name || "").toLowerCase() === "self") || patients[0];
    rememberPatientId(self.id);
    return { patientId: self.id, patients };
  }
  const wanted = explicitId || sessionStorage.getItem("hg_active_patient_id");
  if (wanted && patients.some((p) => p.id === wanted)) {
    rememberPatientId(wanted);
    return { patientId: wanted, patients };
  }
  return { patientId: null, patients };
}

function renderPatientScopeBar(patients, selectedId, hashBase) {
  if (!isClinicianWorkspace()) {
    return `<div class="patient-scope-bar consumer">Working on <strong>your profile</strong> — Discovery and Evidence stay on this one record.</div>`;
  }
  const opts = [`<option value="">Select a patient…</option>`]
    .concat(patients.map((p) => `<option value="${p.id}" ${p.id === selectedId ? "selected" : ""}>${esc(p.display_name)}</option>`))
    .join("");
  return `<div class="patient-scope-bar">
    <label for="patient-scope-select">Active patient</label>
    <select id="patient-scope-select">${opts}</select>
    <a class="app-btn" href="#patients">All patients</a>
  </div>`;
}

function wirePatientScopeSelect(hashBase) {
  const sel = document.getElementById("patient-scope-select");
  if (!sel) return;
  sel.onchange = () => {
    const id = sel.value;
    rememberPatientId(id || null);
    const qs = id ? `?patient=${id}` : "";
    history.replaceState({}, document.title, `#${hashBase}${qs}`);
    render();
  };
}

async function signOut() {
  await Auth.signOut();
  currentUser = null;
  location.href = "/login.html";
}

function esc(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function relTime(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return fmtDate(iso);
}

function fmtConfLabel(n) {
  if (n == null) return "—";
  if (n >= 0.8) return "High";
  if (n >= 0.6) return "Moderate";
  return "Low";
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function patientStatus(p, recentLabs) {
  const processing = (recentLabs || []).some(l =>
    l.patient_id === p.id && (l.status === "parsing" || l.status === "uploaded")
  );
  if (processing) return { label: "PROCESSING", cls: "processing" };
  if (p.lab_report_count === 0) return { label: "NO DATA", cls: "no-data" };
  if (p.lab_report_count > 0 && p.analysis_session_count === 0) return { label: "NEEDS REVIEW", cls: "review" };
  if (p.latest_report_id) return { label: "READY", cls: "ready" };
  return { label: "NO DATA", cls: "no-data" };
}

function primaryFinding(title) {
  if (!title || title === "Analysis Report") return "—";
  const t = title.toLowerCase();
  if (t.includes("iron")) return "Iron deficiency pattern";
  if (t.includes("inflamm")) return "Inflammatory pattern";
  if (t.includes("metabol") || t.includes("glycemic")) return "Metabolic pattern";
  if (t.includes("thyroid")) return "Thyroid-related pattern";
  if (title.length > 48) return title.slice(0, 45) + "…";
  return title.split(".")[0].slice(0, 48);
}

function buildAttentionItems(dash) {
  const items = [];
  for (const p of dash.patients) {
    const st = patientStatus(p, dash.recent_labs);
    if (st.cls === "review") {
      items.push({
        patient: p.display_name,
        patientId: p.id,
        dot: "review",
        title: "New lab data awaiting analysis",
        detail: `${p.lab_report_count} lab report(s) uploaded · analysis not yet run`,
        time: dash.recent_labs.find(l => l.patient_id === p.id)?.created_at,
      });
    } else if (st.cls === "processing") {
      items.push({
        patient: p.display_name,
        patientId: p.id,
        dot: "neutral",
        title: "Lab report processing",
        detail: "Extracting and normalizing biomarkers",
        time: dash.recent_labs.find(l => l.patient_id === p.id)?.created_at,
      });
    }
  }
  for (const s of dash.recent_sessions) {
    if (s.status === "failed") {
      const p = dash.patients.find(x => x.id === s.patient_id);
      items.push({
        patient: p?.display_name || "Patient",
        patientId: s.patient_id,
        dot: "warning",
        title: "Analysis requires review",
        detail: `${s.title} did not complete successfully`,
        time: s.created_at,
      });
    }
  }
  for (const r of dash.recent_reports.slice(0, 3)) {
    if (r.overall_confidence < 0.6) {
      items.push({
        patient: r.patient_display_name || "Patient",
        patientId: r.patient_id,
        dot: "review",
        title: "Evidence coverage may be limited",
        detail: `Analysis confidence: ${fmtConfLabel(r.overall_confidence)} · review recommended`,
        time: r.created_at,
      });
    }
  }
  return items.slice(0, 5);
}

function buildActivityFeed(dash) {
  const events = [];
  for (const r of dash.recent_reports) {
    events.push({ time: r.created_at, label: "Report generated", subject: r.patient_display_name || "Patient", href: `/report.html?report_id=${r.id}` });
  }
  for (const l of dash.recent_labs) {
    const p = dash.patients.find(x => x.id === l.patient_id);
    events.push({ time: l.created_at, label: "Lab report uploaded", subject: p?.display_name || "Patient", href: l.patient_id ? `#patient/${l.patient_id}/labs` : "#upload" });
  }
  for (const s of dash.recent_sessions) {
    const p = dash.patients.find(x => x.id === s.patient_id);
    const label = s.status === "complete" ? "Integrated analysis completed" : s.status === "analyzing" ? "Analysis in progress" : "Analysis session created";
    events.push({ time: s.created_at, label, subject: p?.display_name || s.title, href: s.latest_report_id ? `/report.html?report_id=${s.latest_report_id}` : (s.patient_id ? `#patient/${s.patient_id}/analyses` : "#analysis") });
  }
  events.sort((a, b) => new Date(b.time) - new Date(a.time));
  return events.slice(0, 10);
}

function buildBiologicalSignals(dash) {
  const keywords = [
    { label: "Inflammatory signaling", keys: ["inflamm", "crp", "cytokine"] },
    { label: "Metabolic regulation", keys: ["metabol", "glycemic", "glucose", "hba1c", "lipid"] },
    { label: "Micronutrient insufficiency", keys: ["iron", "vitamin", "ferritin", "b12", "folate"] },
    { label: "Thyroid-related patterns", keys: ["thyroid", "tsh", "t3", "t4"] },
  ];
  const counts = keywords.map(k => ({ ...k, count: 0 }));
  for (const r of dash.recent_reports) {
    const t = (r.title || "").toLowerCase();
    counts.forEach(c => { if (c.keys.some(k => t.includes(k))) c.count += 1; });
  }
  const max = Math.max(1, ...counts.map(c => c.count));
  return counts.map(c => ({ label: c.label, count: c.count, pct: Math.round((c.count / max) * 100) }));
}

function pageHeader(title, subtitle, actionsHtml = "") {
  return `<div class="page-header">
    <div>
      <h1>${title}</h1>
      ${subtitle ? `<p class="page-subtitle">${subtitle}</p>` : ""}
    </div>
    ${actionsHtml ? `<div class="page-header-actions">${actionsHtml}</div>` : ""}
  </div>`;
}

function commandBar() {
  return `<div class="command-bar">
    <a class="app-btn" href="#patients">+ New patient</a>
    <a class="app-btn app-btn-primary" href="#upload">Upload labs</a>
    <a class="app-btn" href="#analysis">Run analysis</a>
    <input class="command-search" id="workspace-search" type="search" placeholder="Search workspace  ⌘K" aria-label="Search workspace">
  </div>`;
}

function renderAttentionList(items) {
  if (!items.length) {
    return `<div class="empty-state" style="padding:1.5rem">
      <p class="muted">No items need attention. Upload labs or run an analysis to get started.</p>
    </div>`;
  }
  return `<div class="attention-list">${items.map(it => `
    <a class="attention-item" href="${it.patientId ? `#patient/${it.patientId}` : '#dashboard'}" style="text-decoration:none;color:inherit">
      <span class="attention-dot ${it.dot}"></span>
      <div class="attention-body">
        <strong>${esc(it.patient)}</strong>
        <p>${esc(it.title)}</p>
        <p>${esc(it.detail)}</p>
        ${it.time ? `<p class="attention-meta">Updated ${relTime(it.time)}</p>` : ""}
      </div>
    </a>`).join("")}</div>`;
}

function renderActivityFeed(events) {
  if (!events.length) return `<p class="muted">No recent activity.</p>`;
  const groups = {};
  for (const e of events) {
    const d = new Date(e.time);
    const key = d.toDateString() === new Date().toDateString() ? "Today" : d.toDateString() === new Date(Date.now() - 86400000).toDateString() ? "Yesterday" : fmtDate(e.time);
    groups[key] = groups[key] || [];
    groups[key].push(e);
  }
  return `<div class="activity-feed">${Object.entries(groups).map(([label, evs]) => `
    <p class="activity-group-label">${esc(label)}</p>
    ${evs.map(e => `
      <a class="activity-item" href="${e.href}" style="text-decoration:none;color:inherit">
        <span class="activity-time">${new Date(e.time).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>
        <span><strong>${esc(e.label)}</strong><br><span class="muted">${esc(e.subject)}</span></span>
      </a>`).join("")}
  `).join("")}</div>`;
}

function renderSignalBars(signals) {
  const hasData = signals.some(s => s.count > 0);
  if (!hasData) {
    return `<div class="empty-state" style="padding:1.25rem">
      <svg class="empty-graph" viewBox="0 0 120 80" aria-hidden="true"><circle cx="30" cy="40" r="8" fill="none" stroke="#2e7d57" stroke-width="1"/><circle cx="60" cy="25" r="8" fill="none" stroke="#6978d8" stroke-width="1"/><circle cx="90" cy="50" r="8" fill="none" stroke="#2e7d57" stroke-width="1"/><line x1="38" y1="38" x2="52" y2="28" stroke="#dde1db" stroke-width="1"/><line x1="68" y1="28" x2="82" y2="46" stroke="#dde1db" stroke-width="1"/></svg>
      <p class="muted">Run analyses to surface biological signals across your workspace.</p>
    </div>`;
  }
  return `<div class="signal-bars">${signals.filter(s => s.count > 0).map(s => `
    <div class="signal-row">
      <span>${esc(s.label)}</span>
      <div class="signal-bar-track"><div class="signal-bar-fill" style="width:${s.pct}%"></div></div>
      <span class="signal-count">${s.count}</span>
    </div>`).join("")}</div>`;
}

function renderOnboardingBanner() {
  const pending = localStorage.getItem("hg_onboarding_pending") === "1"
    || new URLSearchParams(location.search).get("onboard") === "1";
  if (!pending) return "";
  const isClinician = isClinicianWorkspace() || localStorage.getItem("hg_account_type") === "clinician";
  const profileCta = isClinician
    ? `<a class="app-btn app-btn-primary" href="#patients">Add a patient</a>`
    : `<a class="app-btn app-btn-primary" href="#patients">Open my profile</a>`;
  return `
    <div class="app-card onboarding-welcome" style="margin-bottom:1.25rem;border-color:rgba(46,125,87,0.25);background:linear-gradient(180deg,#f8fcf9 0%,#fff 100%)">
      <h2 style="margin:0 0 0.35rem;font-size:1.15rem">${isClinician ? "Welcome to the clinic portal" : "Welcome to your personal portal"}</h2>
      <p class="muted" style="margin:0 0 0.85rem">${isClinician ? "Set up patients first. Discovery and Evidence follow the active record." : "This workspace is only about you. Labs, discovery, and evidence stay on your profile."}</p>
      <ol style="margin:0 0 1rem;padding-left:1.2rem;color:#555;font-size:0.9rem;line-height:1.55">
        <li>Account creation</li>
        <li>Workspace setup</li>
        <li>First analysis</li>
      </ol>
      <div style="display:flex;flex-wrap:wrap;gap:0.5rem">
        ${profileCta}
        <a class="app-btn" href="#upload">Upload your first lab report</a>
        <button type="button" class="app-btn app-btn-ghost" id="dismiss-onboarding">Enter workspace</button>
      </div>
    </div>`;
}

function wireOnboardingBanner() {
  const btn = document.getElementById("dismiss-onboarding");
  if (!btn) return;
  btn.onclick = () => {
    localStorage.removeItem("hg_onboarding_pending");
    const url = new URL(location.href);
    url.searchParams.delete("onboard");
    history.replaceState({}, "", url.pathname + url.search + url.hash);
    btn.closest(".onboarding-welcome")?.remove();
  };
}

function investigationGroupLabel(group) {
  if (group === "core") return "Core evaluation";
  if (group === "directed") return "Directed evaluation";
  if (group === "conditional") return "Conditional evaluation";
  return group;
}

function renderDiscoveryInteraction(body) {
  const interaction = body && body.interaction;
  const current = body && body.current_question;
  const action = body && body.turn_state && body.turn_state.selected_action;
  if (interaction && interaction.type === "file_upload") {
    return `<div class="discovery-question">
      <a class="app-btn app-btn-primary" href="#upload">Upload records</a>
      <a class="app-btn" href="#upload">Add a test manually</a>
    </div>`;
  }
  if (interaction && interaction.type === "single_select" && (interaction.options || []).length) {
    return `<div class="discovery-question" data-question-code="${esc((current && current.code) || "")}">
      <div class="discovery-answer-row">${interaction.options.map((opt) =>
        `<button type="button" class="app-btn" data-select-value="${esc(opt)}">${esc(opt)}</button>`
      ).join("")}</div>
    </div>`;
  }
  if (current && (!action || action.type === "ask_question")) {
    return `<div class="discovery-question" data-question-code="${esc(current.code)}">
      <div class="discovery-answer-row">
        <button type="button" class="app-btn app-btn-primary" data-answer="yes">Yes</button>
        <button type="button" class="app-btn" data-answer="no">No</button>
        <button type="button" class="app-btn app-btn-ghost" data-answer="unknown">Not sure</button>
      </div>
    </div>`;
  }
  return "";
}

function renderDiscoveryChat(body, clinician) {
  const turns = (body && body.turns) || [];
  const action = body && body.turn_state && body.turn_state.selected_action;
  let html = `<div class="discovery-chat" id="discovery-chat">`;
  if (!turns.length) {
    html += `<div class="discovery-bubble system">I will not diagnose. ${clinician ? "What is going on for this patient?" : "What is going on?"}</div>`;
  }
  if (action && action.type === "show_safety_message") {
    html += `<div class="discovery-bubble system discovery-safety">Safety pause — Discovery will not continue until this is evaluated in person.</div>`;
  }
  const lastSystem = [...turns].reverse().find((t) => t.role === "system");
  for (const turn of turns) {
    html += `<div class="discovery-bubble ${turn.role === "user" ? "user" : "system"}">${esc(turn.text)}`;
    if (turn === lastSystem) html += renderDiscoveryInteraction(body);
    html += `</div>`;
  }
  html += `</div>`;
  return html;
}

function renderDiscoveryCase(body) {
  if (!body) return "";
  const hypos = body.hypotheses || [];
  const branches = body.branch_coverage || [];
  const outcomes = body.outcomes || [];
  let html = `<p class="page-subtitle">${esc(body.disclaimer || "")}</p>`;
  html += `<div class="metric-grid">`;
  html += `<div class="metric-card"><div class="metric-label">Investigation coverage</div><div class="metric-value">${body.investigation_coverage_percent || 0}%</div><div class="metric-delta">Not disease probability</div></div>`;
  html += `<div class="metric-card"><div class="metric-label">Open hypotheses</div><div class="metric-value">${hypos.length}</div><div class="metric-delta">None are diagnoses</div></div>`;
  html += `<div class="metric-card"><div class="metric-label">Recorded checks</div><div class="metric-value">${outcomes.length}</div><div class="metric-delta">Outcomes, not conclusions</div></div>`;
  html += `</div>`;
  const changed = body.what_changed || [];
  if (changed.length) {
    html += `<div class="wallet-card"><h2>What changed</h2><ul>`;
    for (const line of changed) html += `<li>${esc(line)}</li>`;
    html += `</ul></div>`;
  }
  const plan = body.monitor_plan || [];
  if (plan.length) {
    html += `<div class="wallet-card"><h2>Next useful checks</h2><p class="muted">Only if a result would change management. Not a hunt for 90% confidence.</p><ul>`;
    for (const item of plan) {
      html += `<li><strong>${esc(item.label)}</strong> <span class="muted">(${esc(item.group)})</span> — ${esc(item.reason)}</li>`;
    }
    html += `</ul></div>`;
  }
  if (branches.length) {
    html += `<div class="wallet-card"><h2>Branch coverage</h2>`;
    for (const row of branches) {
      html += `<div class="signal-row"><span>${esc(row.label)}</span><span class="mono">${row.coverage_percent}%</span></div>`;
      html += `<div class="signal-bar-track"><div class="signal-bar-fill" style="width:${row.coverage_percent}%"></div></div>`;
    }
    html += `</div>`;
  }
  if (outcomes.length) {
    html += `<div class="wallet-card"><h2>Outcomes</h2><ul>`;
    for (const row of outcomes) {
      html += `<li><strong>${esc(row.label)}</strong> <span class="status-chip ${row.status === "completed" ? "ready" : "review"}">${esc(row.status)}</span></li>`;
    }
    html += `</ul></div>`;
  }
  for (const h of hypos) {
    html += `<article class="wallet-card">`;
    html += `<h2>${esc(h.label)}</h2>`;
    html += `<p class="muted">Relevance ${h.investigation_relevance_percent}% · Coverage ${h.investigation_coverage_percent}%</p>`;
    html += `<p class="muted">${esc(h.not_a_diagnosis || "")}</p>`;
    if ((h.why_limited || []).length) {
      html += `<ul>${h.why_limited.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`;
    }
    const groups = ["core", "directed", "conditional"];
    for (const group of groups) {
      const items = (h.investigations || []).filter((i) => i.group === group);
      if (!items.length) continue;
      html += `<h3>${investigationGroupLabel(group)}</h3><ul>`;
      for (const item of items) {
        html += `<li>${esc(item.label)}${item.already_assessed ? " <span class=\"status-chip ready\">assessed</span>" : ""}</li>`;
      }
      html += `</ul>`;
    }
    html += `</article>`;
  }
  return html;
}

function provenanceBadge(level) {
  const label = level === "verified" ? "Verified" : level === "inferred" ? "Inferred" : "Reported";
  return `<span class="prov-badge ${esc(level || "reported")}">${label}</span>`;
}

function renderControlBanner(body) {
  const turn = (body && body.turn_state) || {};
  const paused = turn.paused_concerns || [];
  const mode = turn.response_mode || "";
  if (!paused.length && !mode) return "";
  const pausedLabel = paused.join(", ").split("_").join(" ");
  return `<div class="discovery-control-banner" data-discovery-control="1">
    ${mode ? `<p><strong>Response mode</strong> ${esc(mode)}</p>` : ""}
    ${paused.length ? `<p>Paused: ${esc(pausedLabel)}. Ask will not return to a paused concern unless you resume it or safety requires it.</p>` : ""}
  </div>`;
}

function renderSafetyBanner(body) {
  const state = (body.turn_state && body.turn_state.safety_status) || (body.safety && body.safety.state);
  if (!state || state === "S0") return "";
  const net = (body.turn_state && body.turn_state.safety_net) || (body.safety && body.safety.safety_net) || {};
  const watch = (net.watch_for || []).slice(0, 5).map((item) => esc(item)).join("; ");
  const canContinue = body.turn_state ? body.turn_state.discovery_can_continue !== false : true;
  const label = {
    S1: "Safety information incomplete — clarifying before any disposition.",
    S2: "Routine clinical follow-up is reasonable. Discovery can continue.",
    S3: "Prompt in-person assessment is advised. Only limited continuation here.",
    S4: "Urgent in-person evaluation is advised. Discovery is paused.",
  }[state] || "";
  if (!label) return "";
  return `<div class="safety-banner" data-safety-state="${esc(state)}">
    <p><strong>${esc(state)}</strong> ${label}</p>
    ${watch && canContinue ? `<p class="muted">If the pattern changes — ${watch} — seek prompt medical evaluation.</p>` : ""}
  </div>`;
}

function renderAtlasMemory(body) {
  if (!body) {
    return `<aside class="atlas-panel atlas-memory" data-atlas-panel="memory">
      <h2>Health memory</h2>
      <p class="muted">Nothing stored yet. The Case fills this as you talk. Nothing here is a diagnosis.</p>
    </aside>`;
  }
  const memory = body.memory_items || [];
  const timeline = body.timeline || [];
  const workup = body.prior_workup || [];
  const memRows = memory.map((item) =>
    `<li><strong>${esc(item.name)}</strong> ${esc(item.value || "")} ${provenanceBadge(item.provenance)}</li>`
  ).join("") || "<li class=\"muted\">No structured facts yet.</li>";
  const timeRows = timeline.map((item) =>
    `<li>${esc(item.name)}: ${esc(item.value || "")} ${provenanceBadge(item.provenance)}</li>`
  ).join("") || "<li class=\"muted\">Chronology not established.</li>";
  const workRows = workup.map((item) =>
    `<li>${esc(item.name)}: ${esc(item.value || "")} <span class="prov-badge reported">Patient-reported</span></li>`
  ).join("") || "<li class=\"muted\">Prior workup unknown — not the same as “labs were normal.”</li>";
  return `<aside class="atlas-panel atlas-memory" data-atlas-panel="memory">
    <h2>What HerbaGraph knows</h2>
    ${body.problem_representation ? `<p class="discovery-problem">${esc(body.problem_representation)}</p>` : ""}
    ${renderControlBanner(body)}
    ${renderSafetyBanner(body)}
    <h3>Facts</h3><ul>${memRows}</ul>
    <h3>Timeline</h3><ul>${timeRows}</ul>
    <h3>Prior workup</h3><ul>${workRows}</ul>
  </aside>`;
}

function renderAtlasInvestigation(body) {
  if (!body) {
    return `<aside class="atlas-panel atlas-investigate" data-atlas-panel="investigate">
      <h2>Investigation</h2>
      <p class="muted">Branches appear after a concern is opened. Relevance is not a diagnosis.</p>
    </aside>`;
  }
  const explanation = body.explanation || {};
  const families = explanation.families || [];
  const hypos = families.length ? families : (body.hypotheses || []);
  const increasers = (explanation.ranked_actions && explanation.ranked_actions.length) ? explanation.ranked_actions : (body.confidence_increasers || []);
  const action = body.turn_state && body.turn_state.selected_action;
  const hypoRows = hypos.map((h) => {
    const id = h.id || h.code || "";
    const evals = (h.evaluations || []).slice(0, 6).map((item) =>
      `<li data-candidate-id="${esc(item.id || "")}"><strong>${esc(item.label)}</strong> <span class="muted">${esc(item.coverage_relation || "")}. ${esc(item.can_tell || "")} Cannot tell: ${esc(item.cannot_tell || "")}</span></li>`
    ).join("");
    return `<li data-family-id="${esc(id)}"><strong>${esc(h.label)}</strong><br>
      <span class="muted">${h.relationship ? esc(h.relationship) + " · " : ""}Coverage is completeness, not probability — not a diagnosis</span>
      <details class="ask-why-drawer" data-explanation-drawer="1">
        <summary>Why is this here?</summary>
        <p>${esc(h.rationale || (h.why_limited && h.why_limited[0]) || h.not_a_diagnosis || "Open because related findings are present.")}</p>
        ${h.unknowns && h.unknowns.length ? `<p>Still unknown: ${esc(h.unknowns.slice(0, 4).join(", "))}</p>` : ""}
        <p><strong>Ways to evaluate</strong></p><ul>${evals || '<li class="muted">No ranked options yet.</li>'}</ul>
        <p><strong>Research</strong></p>
        <ul>${(h.claim_card_ids || []).map((id) => `<li data-evidence-id="${esc(id)}">${esc(id)}</li>`).join("") || '<li class="muted">No stored citation supports this statement. Missing literature stays a limitation.</li>'}</ul>
        <p>${esc(h.next_action || "Prepare for clinician")}</p>
      </details></li>`;
  }).join("") || "<li class=\"muted\">No investigation family activated.</li>";
  const gapRows = increasers.map((item) =>
    `<li data-candidate-id="${esc(item.id || "")}"><strong>${esc(item.label)}</strong> <span class="muted">${esc(item.why || item.reason || "")}</span></li>`
  ).join("") || "<li class=\"muted\">No ranked confidence gaps yet.</li>";
  return `<aside class="atlas-panel atlas-investigate" data-atlas-panel="investigate">
    <h2>What we're investigating</h2>
    <p class="muted">Map v${body.map_version || 1}. Coverage is how thoroughly a branch was assessed.</p>
    ${action ? `<div class="next-action-card"><strong>Next</strong> ${esc(action.objective || action.type)}</div>` : ""}
    <h3>Branches</h3><ul>${hypoRows}</ul>
    <h3>What would increase confidence</h3><ul>${gapRows}</ul>
  </aside>`;
}

function renderDisclaimerGate() {
  if (localStorage.getItem("hg_discovery_disclaimer_v1") === "1") return "";
  return `<div class="wallet-card discovery-disclaimer" id="discovery-disclaimer">
    <p>HerbaGraph Discovery is an educational health-information and investigation tool. It helps organize health history, explore evidence, and identify questions or evaluations that may be worth discussing. It does not provide a medical diagnosis and does not replace care from a qualified healthcare professional.</p>
    <button type="button" class="app-btn app-btn-primary" id="ack-discovery-disclaimer">I understand</button>
  </div>`;
}

async function renderDiscovery(caseId, requestedPatientId) {
  const { patientId, patients } = await resolveActivePatientId(requestedPatientId);
  const clinician = isClinicianWorkspace();
  let current = null;
  let cases = [];
  if (caseId) {
    try {
      current = await api(`/api/v1/cases/${caseId}`);
      if (current.patient_id) rememberPatientId(current.patient_id);
    } catch (_) {
      current = null;
    }
  }
  const scopeId = (current && current.patient_id) || patientId;
  if (scopeId) {
    cases = await api(`/api/v1/cases?patient_id=${scopeId}`);
    if (!current && cases.length) current = cases[0];
  }

  const subtitle = clinician
    ? "Each case belongs to one patient. Select the person first — this is not a personal journal."
    : "This investigation is about you. Relevance means worth looking into, not a diagnosis.";

  let caseList = "";
  if (scopeId && cases.length) {
    caseList = `<div class="wallet-card"><h2>${clinician ? "Cases for this patient" : "Your cases"}</h2><ul>${cases.map((c) =>
      `<li><a href="#discovery?case=${c.id}${scopeId ? `&patient=${scopeId}` : ""}">${esc((c.presenting_concern || "Untitled").slice(0, 90))}</a></li>`
    ).join("")}</ul></div>`;
  }

  const formDisabled = clinician && !scopeId;
  const chatPlaceholder = current && current.current_question
    ? "Yes, no, not sure — or add a note"
    : (clinician ? "Describe this patient's concern…" : "What's going on?");
  document.getElementById("app-main").innerHTML = `
    ${pageHeader(clinician ? "Clinic Discovery" : "My discovery", subtitle)}
    ${renderPatientScopeBar(patients, scopeId, "discovery")}
    ${renderDisclaimerGate()}
    ${formDisabled ? `<p class="muted">Select a patient to open Discovery. A clinician workspace cannot run a case without a patient.</p>` : `
    <nav class="atlas-mobile-tabs" aria-label="Discovery views">
      <button type="button" class="atlas-tab active" data-atlas-tab="chat">Chat</button>
      <button type="button" class="atlas-tab" data-atlas-tab="memory">Memory</button>
      <button type="button" class="atlas-tab" data-atlas-tab="investigate">Investigation</button>
    </nav>
    <div class="atlas-workspace" id="atlas-workspace">
      ${renderAtlasMemory(current)}
      <section class="atlas-panel atlas-chat" data-atlas-panel="chat">
        <p class="muted discovery-interface-note">Chat is only an interface — the Case is the source of truth. Every turn updates the Case first. Not a diagnosis.</p>
        ${renderDiscoveryChat(current, clinician)}
        <form class="discovery-composer" id="discovery-open-form">
          <label class="sr-only" for="discovery-concern">${current ? "Your reply" : "What is going on?"}</label>
          <textarea id="discovery-concern" rows="2" required placeholder="${esc(chatPlaceholder)}"></textarea>
          <button class="app-btn app-btn-primary" type="submit" id="discovery-open-btn">Send</button>
        </form>
      </section>
      ${renderAtlasInvestigation(current)}
    </div>`}
    ${caseList}
    <details class="wallet-card discovery-case-board" id="discovery-result" ${current && current.turn_state && current.turn_state.selected_action && current.turn_state.selected_action.type === "show_investigation_map" ? "open" : ""} ${current ? "" : "hidden"}>
      <summary>Investigation map — branches and gaps, not a diagnosis</summary>
      ${current ? renderDiscoveryCase(current) : ""}
    </details>
  `;
  wirePatientScopeSelect("discovery");
  wireDiscoveryAnswers();
  wireAtlasTabs();
  const ack = document.getElementById("ack-discovery-disclaimer");
  if (ack) {
    ack.onclick = () => {
      localStorage.setItem("hg_discovery_disclaimer_v1", "1");
      document.getElementById("discovery-disclaimer")?.remove();
    };
  }
  const chat = document.getElementById("discovery-chat");
  if (chat) chat.scrollTop = chat.scrollHeight;
  const form = document.getElementById("discovery-open-form");
  if (!form) return;
  const box = document.getElementById("discovery-concern");
  if (box) {
    box.focus();
    box.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const concern = document.getElementById("discovery-concern").value.trim();
    const btn = document.getElementById("discovery-open-btn");
    btn.disabled = true;
    try {
      let body;
      if (current && current.id) {
        body = await api(`/api/v1/cases/${current.id}/turns`, "POST", { text: concern });
      } else {
        body = await api("/api/v1/cases", "POST", { presenting_concern: concern, patient_id: scopeId });
      }
      current = body;
      const qs = new URLSearchParams({ case: body.id });
      if (scopeId) qs.set("patient", scopeId);
      history.replaceState({}, document.title, `#discovery?${qs}`);
      await renderDiscovery(body.id, scopeId);
    } catch (err) {
      const board = document.getElementById("discovery-result");
      if (board) board.innerHTML = `<p class="muted">${esc(err.message || "Could not update case")}</p>`;
      btn.disabled = false;
    }
  });
}

function wireAtlasTabs() {
  const tabs = document.querySelectorAll("[data-atlas-tab]");
  if (!tabs.length) return;
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const name = tab.getAttribute("data-atlas-tab");
      document.querySelectorAll("[data-atlas-tab]").forEach((btn) => btn.classList.toggle("active", btn === tab));
      document.querySelectorAll("[data-atlas-panel]").forEach((panel) => {
        panel.classList.toggle("atlas-panel-active", panel.getAttribute("data-atlas-panel") === name);
      });
    });
  });
}

function wireDiscoveryAnswers() {
  const caseMatch = /case=([^&]+)/.exec(location.hash);
  const sendTurn = async (text, btn) => {
    if (!caseMatch) return;
    if (btn) btn.disabled = true;
    try {
      const body = await api(`/api/v1/cases/${caseMatch[1]}/turns`, "POST", { text });
      const patientMatch = /patient=([^&]+)/.exec(location.hash);
      await renderDiscovery(body.id, patientMatch ? patientMatch[1] : null);
    } catch (err) {
      const board = document.getElementById("discovery-result");
      if (board) board.innerHTML = `<p class="muted">${esc(err.message || "Could not record answer")}</p>`;
      if (btn) btn.disabled = false;
    }
  };
  document.querySelectorAll("[data-select-value]").forEach((btn) => {
    btn.addEventListener("click", () => sendTurn(btn.getAttribute("data-select-value"), btn));
  });
  document.querySelectorAll("[data-answer]").forEach((btn) => {
    btn.addEventListener("click", () => sendTurn(btn.textContent.trim(), btn));
  });
}

function clinicPatientRows(dash) {
  return dash.patients.map(p => {
    const st = patientStatus(p, dash.recent_labs);
    const report = dash.recent_reports.find(r => r.patient_id === p.id);
    return `<tr data-href="#patient/${p.id}">
      <td><a class="row-link" href="#patient/${p.id}">${esc(p.display_name)}</a></td>
      <td class="mono">${p.lab_report_count}</td>
      <td class="mono">${p.analysis_session_count}</td>
      <td>${report ? esc(primaryFinding(report.title)) : "—"}</td>
      <td><span class="status-chip ${st.cls}">${st.label}</span></td>
      <td class="mono">${report ? relTime(report.created_at) : "—"}</td>
    </tr>`;
  }).join("") || `<tr class="no-hover"><td colspan="6" class="muted">No patients yet</td></tr>`;
}

function reportRowsHtml(dash, clinician) {
  return dash.recent_reports.map(r => `
    <tr data-href="/report.html?report_id=${r.id}">
      ${clinician ? `<td>${esc(r.patient_display_name || "—")}</td>` : ""}
      <td>${esc(primaryFinding(r.title))}</td>
      <td><span class="status-chip ready">${fmtConfLabel(r.overall_confidence)}</span></td>
      <td class="mono">${fmtDate(r.created_at)}</td>
      <td><a href="/report.html?report_id=${r.id}">View report</a></td>
    </tr>`).join("") || `<tr class="no-hover"><td colspan="${clinician ? 5 : 4}" class="muted">No reports yet</td></tr>`;
}

function renderLaunchCards() {
  const pid = sessionStorage.getItem("hg_active_patient_id");
  const ask = pid ? `/ask.html?patient=${pid}` : "/ask.html";
  return `<div class="launch-grid">
    <a class="launch-card" href="${ask}">
      <h2>Talk to Discovery Guide</h2>
      <p>Tell the investigation guide what's been going on. This opens Ask — it does not replace this workspace.</p>
    </a>
    <a class="launch-card" href="#upload">
      <h2>Analyze my labs</h2>
      <p>Existing workflow. Upload, parse, pathways, and reports stay here.</p>
    </a>
    <a class="launch-card" href="${ask}">
      <h2>My investigations</h2>
      <p>Continue a Discovery case. Results still return to this portal.</p>
    </a>
  </div>`;
}

function renderClinicDashboard(dash, name) {
  const activeAnalyses = dash.recent_sessions.filter(s => s.status === "analyzing" || s.status === "pending").length;
  const needsReview = buildAttentionItems(dash).length;
  return `
    ${renderOnboardingBanner()}
    ${pageHeader(`${greeting()}${name}`, "Clinic portal — lab analysis, patients, and reports stay here. Discovery is an added layer.", `<a class="app-btn app-btn-primary" href="#patients">Add patient</a>`)}
    ${commandBar()}
    ${renderLaunchCards()}
    <div class="metric-grid">
      <div class="metric-card"><div class="metric-label">Patients</div><div class="metric-value">${dash.patients.length}</div><div class="metric-delta">In this clinic</div></div>
      <div class="metric-card"><div class="metric-label">Active analyses</div><div class="metric-value">${activeAnalyses}</div><div class="metric-delta">${activeAnalyses ? "Processing" : "None running"}</div></div>
      <div class="metric-card"><div class="metric-label">Reports</div><div class="metric-value">${dash.recent_reports.length}</div><div class="metric-delta">Recent analyses</div></div>
      <div class="metric-card"><div class="metric-label">Needs review</div><div class="metric-value">${needsReview}</div><div class="metric-delta">Attention items</div></div>
    </div>
    <div class="workspace-section">
      <h2>Needs attention</h2>
      ${renderAttentionList(buildAttentionItems(dash))}
    </div>
    <div class="workspace-section">
      <h2>Recent patients</h2>
      <div class="data-table-wrap"><table class="data-table"><thead><tr>
        <th>Patient</th><th>Labs</th><th>Analyses</th><th>Latest report</th><th>Status</th><th>Updated</th>
      </tr></thead><tbody>${clinicPatientRows(dash)}</tbody></table></div>
    </div>
    <div class="workspace-section">
      <h2>Recent reports</h2>
      <div class="data-table-wrap"><table class="data-table"><thead><tr>
        <th>Patient</th><th>Primary finding</th><th>Confidence</th><th>Created</th><th></th>
      </tr></thead><tbody>${reportRowsHtml(dash, true)}</tbody></table></div>
    </div>
    <div class="form-grid-2" style="margin-top:0.5rem">
      <div class="workspace-section">
        <h2>Biological signals across the clinic</h2>
        <div class="app-card">${renderSignalBars(buildBiologicalSignals(dash))}</div>
      </div>
      <div class="workspace-section">
        <h2>Recent activity</h2>
        <div class="app-card">${renderActivityFeed(buildActivityFeed(dash))}</div>
      </div>
    </div>`;
}

function renderPersonalDashboard(dash, name) {
  const latest = dash.recent_reports[0];
  const labs = dash.recent_labs || [];
  const needsReview = buildAttentionItems(dash).length;
  return `
    ${renderOnboardingBanner()}
    ${pageHeader(`${greeting()}${name}`, "Personal portal — labs, reports, and analysis stay here. Ask is an added layer.", `<a class="app-btn app-btn-primary" href="#upload">Upload my labs</a>`)}
    ${commandBar()}
    ${renderLaunchCards()}
    <div class="metric-grid">
      <div class="metric-card"><div class="metric-label">Your profile</div><div class="metric-value">Self</div><div class="metric-delta">Personal record</div></div>
      <div class="metric-card"><div class="metric-label">Labs</div><div class="metric-value">${labs.length}</div><div class="metric-delta">Uploaded files</div></div>
      <div class="metric-card"><div class="metric-label">Reports</div><div class="metric-value">${dash.recent_reports.length}</div><div class="metric-delta">Your analyses</div></div>
      <div class="metric-card"><div class="metric-label">Needs review</div><div class="metric-value">${needsReview}</div><div class="metric-delta">Attention items</div></div>
    </div>
    <div class="form-grid-2">
      <div class="app-card" id="workspace-test-plan">
        <h2>Testing plan from Discovery</h2>
        <p class="muted">Recommended by Ask. Upload or analyze them in this workspace — not a new product.</p>
        <div id="test-plan-mount"><p class="muted">Loading…</p></div>
      </div>
      <div class="app-card">
        <h2>Latest report</h2>
        ${latest
          ? `<p>${esc(primaryFinding(latest.title))}</p><a class="app-btn" href="/report.html?report_id=${latest.id}">Open my report</a>`
          : `<p class="muted">No report yet. Upload labs to run your first analysis.</p>`}
      </div>
    </div>
    <div class="workspace-section">
      <h2>Needs attention</h2>
      ${renderAttentionList(buildAttentionItems(dash))}
    </div>
    <div class="workspace-section">
      <h2>My reports</h2>
      <div class="data-table-wrap"><table class="data-table"><thead><tr>
        <th>Primary finding</th><th>Confidence</th><th>Created</th><th></th>
      </tr></thead><tbody>${reportRowsHtml(dash, false)}</tbody></table></div>
    </div>
    <div class="form-grid-2" style="margin-top:0.5rem">
      <div class="workspace-section">
        <h2>Your biological signals</h2>
        <div class="app-card">${renderSignalBars(buildBiologicalSignals(dash))}</div>
      </div>
      <div class="workspace-section">
        <h2>Recent activity</h2>
        <div class="app-card">${renderActivityFeed(buildActivityFeed(dash))}</div>
      </div>
    </div>`;
}

async function renderDashboard() {
  const dash = await api("/api/v1/workspace/dashboard");
  lastDashboard = dash;
  const name = dash.user_full_name ? `, ${esc(dash.user_full_name)}` : "";
  document.getElementById("app-main").innerHTML = isClinicianWorkspace()
    ? renderClinicDashboard(dash, name)
    : renderPersonalDashboard(dash, name);
  wireTableRows();
  wireCommandSearch(dash);
  wireOnboardingBanner();
  fillTestPlanMount(null);
}

async function fillSnapshotMount(patientId) {
  const mount = document.getElementById("snapshot-mount");
  if (!mount || !patientId) return;
  try {
    const snap = await api(`/api/v1/patients/${patientId}/longitudinal-snapshot`);
    const payload = snap.payload || {};
    const list = (items, empty) =>
      (items || []).length
        ? `<ul class="test-plan-list">${items.slice(0, 8).map((item) =>
            `<li>${esc(typeof item === "string" ? item : (item.name ? `${item.name}: ${item.value || item.status || ""}` : JSON.stringify(item)))}</li>`
          ).join("")}</ul>`
        : `<p class="muted">${empty}</p>`;
    mount.innerHTML = `
      <p class="muted">Snapshot v${esc(snap.version)} · derived from labs and cases</p>
      <p><strong>Concerns</strong></p>
      ${list(payload.current_concerns, "No recorded concerns yet.")}
      <p><strong>Lab trends</strong></p>
      ${list(payload.lab_trends, "No labs in memory yet.")}
      <p><strong>Medications</strong></p>
      ${list(payload.medications, "No medications recorded.")}
      <p><strong>Other diagnostics</strong></p>
      ${list(payload.other_diagnostics, "No EMG or imaging reports attached.")}
      <button type="button" class="app-btn" id="refresh-snapshot">Refresh memory</button>`;
    const btn = document.getElementById("refresh-snapshot");
    if (btn) {
      btn.onclick = async () => {
        btn.disabled = true;
        try {
          await api(`/api/v1/patients/${patientId}/longitudinal-snapshot`, "POST", {});
          await fillSnapshotMount(patientId);
        } catch (_) {
          btn.disabled = false;
        }
      };
    }
  } catch (_) {
    mount.innerHTML = `<p class="muted">Longitudinal memory unavailable.</p>`;
  }
}

async function fillTestPlanMount(patientId) {
  const mount = document.getElementById("test-plan-mount");
  if (!mount) return;
  try {
    const qs = patientId ? `?patient_id=${patientId}` : "";
    const rows = await api(`/api/v1/cases/plan${qs}`);
    if (!rows.length) {
      mount.innerHTML = `<p class="muted">Nothing added from Discovery yet.</p>`;
      return;
    }
    mount.innerHTML = `<ul class="test-plan-list">${rows.map((row) =>
      `<li><label><input type="checkbox" checked disabled> ${esc(row.label)}</label> <span class="muted">${esc(row.reason || "Recommended by Discovery")}</span></li>`
    ).join("")}</ul>
    <a class="app-btn" href="#upload${patientId ? `?patient=${patientId}` : ""}">Upload these results</a>`;
  } catch (_) {
    mount.innerHTML = `<p class="muted">Testing plan unavailable.</p>`;
  }
}

async function renderPatients() {
  const patients = await api("/api/v1/patients");
  const dash = lastDashboard || await api("/api/v1/workspace/dashboard");
  const rows = patients.map(p => {
    const summary = dash.patients.find(x => x.id === p.id) || p;
    const st = patientStatus(summary, dash.recent_labs || []);
    return `<tr data-href="#patient/${p.id}">
      <td><a class="row-link" href="#patient/${p.id}">${esc(p.display_name)}</a></td>
      <td class="mono">${summary.lab_report_count ?? 0}</td>
      <td class="mono">${summary.analysis_session_count ?? 0}</td>
      <td>${p.age ?? "—"}</td>
      <td>${esc(p.biological_sex || "—")}</td>
      <td><span class="status-chip ${st.cls}">${st.label}</span></td>
      <td class="mono">${fmtDate(p.created_at)}</td>
    </tr>`;
  }).join("") || `<tr class="no-hover"><td colspan="7" class="muted">No patients yet</td></tr>`;

  if (!isClinicianWorkspace() && patients.length === 1) {
    location.hash = `#patient/${patients[0].id}`;
    return;
  }

  document.getElementById("app-main").innerHTML = `
    ${pageHeader(isClinicianWorkspace() ? "Patients" : "My profile", isClinicianWorkspace() ? "One clinician, many patient records. Discovery and Evidence follow the active patient." : "Your biological profile.")}
    <div class="form-grid-2">
      <div class="app-card" ${isClinicianWorkspace() ? "" : "hidden"}>
        <h2 style="margin:0 0 0.75rem;font-size:1rem">Create patient</h2>
        <div class="form-row"><label>Display name</label><input id="new-patient-name" value="Patient A"></div>
        <div class="form-grid-2">
          <div class="form-row"><label>Age (optional)</label><input id="new-patient-age" type="number"></div>
          <div class="form-row"><label>Sex (optional)</label><select id="new-patient-sex"><option value="">—</option><option>female</option><option>male</option></select></div>
        </div>
        <button class="app-btn app-btn-primary" id="create-patient-btn">Create patient</button>
        <p id="patient-create-error" class="error"></p>
      </div>
      <div>
        <div class="data-table-wrap"><table class="data-table"><thead><tr>
          <th>Name</th><th>Labs</th><th>Analyses</th><th>Age</th><th>Sex</th><th>Status</th><th>Created</th>
        </tr></thead><tbody>${rows}</tbody></table></div>
      </div>
    </div>`;
  wireTableRows();
  document.getElementById("create-patient-btn").onclick = async () => {
    try {
      const p = await api("/api/v1/patients", "POST", {
        display_name: document.getElementById("new-patient-name").value.trim() || "Patient",
        age: document.getElementById("new-patient-age").value ? Number(document.getElementById("new-patient-age").value) : null,
        biological_sex: document.getElementById("new-patient-sex").value || null,
      });
      location.hash = `#patient/${p.id}`;
      render();
    } catch (e) {
      document.getElementById("patient-create-error").textContent = e.message;
    }
  };
}

function buildAnalysisFindingsHtml(report) {
  const systems = (report.biological_systems || []).slice(0, 4);
  const biomarkers = ((report.biomarker_summary || {}).measured_biomarkers || [])
    .filter(b => b.status && b.status !== "normal").slice(0, 5);
  const recs = (report.recommendations || []).slice(0, 4);
  let html = `<div class="analysis-findings-list">`;
  if (systems.length) {
    html += `<p class="muted" style="margin:0 0 0.35rem;font-size:0.78rem">Biological systems</p>`;
    systems.forEach(s => {
      html += `<div class="analysis-finding-item" data-finding-type="system" data-finding-label="${esc(s.system_name)}">
        <strong>${esc(s.system_name)}</strong><br><span class="muted">${esc(s.signal_label || "")} · ${esc((s.drivers || []).join(", "))}</span>
      </div>`;
    });
  }
  if (biomarkers.length) {
    html += `<p class="muted" style="margin:0.75rem 0 0.35rem;font-size:0.78rem">Key biomarkers</p>`;
    biomarkers.forEach(b => {
      html += `<div class="analysis-finding-item" data-finding-type="biomarker" data-finding-label="${esc(b.biomarker_name)}">
        <span class="mono">${esc(b.biomarker_name)}</span> <span class="mono">${b.value} ${esc(b.unit || "")}</span> · ${esc(b.status)}
      </div>`;
    });
  }
  if (recs.length) {
    html += `<p class="muted" style="margin:0.75rem 0 0.35rem;font-size:0.78rem">Intervention candidates</p>`;
    recs.forEach(r => {
      html += `<div class="analysis-finding-item" data-finding-type="intervention" data-finding-label="${esc(r.intervention_name)}" data-rec-index="${r.rank || 0}">
        <strong>${esc(r.intervention_name)}</strong><br><span class="muted">${esc(r.evidence_tier_label || r.evidence_level || "")}</span>
      </div>`;
    });
  }
  html += `</div>`;
  return html;
}

function analysisGraphShell(title) {
  return `<div class="reasoning-panel" style="margin-bottom:1.25rem">
    <div class="app-card">
      <h3 style="margin:0 0 0.75rem;font-size:0.95rem">${esc(title)}</h3>
      <div id="analysis-findings-panel"></div>
      <div id="analysis-path-panel" class="reasoning-path" style="display:none"></div>
    </div>
    <div class="app-card reasoning-graph-panel">
      <h3>Reasoning graph</h3>
      <div class="reasoning-graph-layout">
        <div class="reasoning-graph-mount" id="analysis-graph-mount"></div>
        <div class="reasoning-graph-detail" data-graph-detail>Click a node to inspect the reasoning path.</div>
      </div>
    </div>
  </div>`;
}

function mountAnalysisGraph(report) {
  const RG = window.HerbaGraphReasoningGraph;
  if (!RG || !report) return;
  const findings = document.getElementById("analysis-findings-panel");
  if (findings) findings.innerHTML = buildAnalysisFindingsHtml(report);
  const graph = RG.buildFromReport(report);
  const controller = RG.mount(document.getElementById("analysis-graph-mount"), graph, {
    onSelect(node) {
      const pathPanel = document.getElementById("analysis-path-panel");
      if (pathPanel && node.recommendation) {
        pathPanel.style.display = "block";
        const steps = RG.buildReasoningPathSteps(report, node.recommendation);
        pathPanel.innerHTML = `<p class="reasoning-path-title">Reasoning path · ${esc(node.recommendation.intervention_name)}</p>${RG.renderPathHtml(steps, { interactive: false })}`;
      }
      document.querySelectorAll(".analysis-finding-item").forEach(el => {
        el.classList.toggle("is-active", el.dataset.findingLabel === node.label);
      });
    },
  });
  document.querySelectorAll(".analysis-finding-item").forEach(el => {
    el.addEventListener("click", () => {
      const label = el.dataset.findingLabel;
      const match = graph.nodes.find(n => n.label === label);
      if (match && controller) controller.highlight(match.id);
    });
  });
}

async function buildAnalysisWorkspace(patientId, overview, sessionRows) {
  let workspace = "";
  if (overview.latest_report_id) {
    try {
      const report = await api(`/api/v1/reports/${overview.latest_report_id}`);
      window._pendingAnalysisReport = report;
      workspace = analysisGraphShell("Analysis summary") + `
        <p style="margin:0 0 0.75rem"><a class="app-btn app-btn-primary" href="/report.html?report_id=${overview.latest_report_id}">Open full clinical report</a></p>`;
    } catch (_) {
      workspace = `<div class="app-card empty-state"><p class="muted">Could not load analysis report. Try opening from the sessions table below.</p></div>`;
    }
  } else {
    workspace = `<div class="app-card empty-state">
      <h3>No analysis yet</h3>
      <p>Upload labs and run an integrated analysis to open the reasoning workspace.</p>
      <a class="app-btn app-btn-primary" href="#analysis?patient=${patientId}">Run analysis</a>
    </div>`;
  }
  return `${workspace}
    <div class="workspace-section">
      <h2>Analysis history</h2>
      <div class="data-table-wrap"><table class="data-table"><thead><tr><th>Title</th><th>Type</th><th>Status</th><th>Confidence</th><th></th></tr></thead><tbody>${sessionRows}</tbody></table></div>
      <p style="margin-top:0.75rem"><a class="app-btn app-btn-primary" href="#analysis?patient=${patientId}">Run integrated analysis</a></p>
    </div>`;
}

async function renderPatient(patientId, section = "overview") {
  const overview = await api(`/api/v1/workspace/patients/${patientId}/overview`);
  const sexAge = [overview.biological_sex, overview.age ? `${overview.age}` : null].filter(Boolean).join(" · ");
  const tabs = [
    ["overview", "Overview"],
    ["labs", "Labs"],
    ["analyses", "Analysis"],
    ["context", "Context"],
  ];

  const labRows = overview.lab_reports.map(l => `
    <tr data-href="#review/${l.id}" data-lab-id="${l.id}">
      <td class="lab-select-cell" onclick="event.stopPropagation()">
        <input type="checkbox" class="lab-select-cb" value="${l.id}" aria-label="Select ${esc(l.original_filename)}">
      </td>
      <td>
        <div class="lab-file-name">${esc(l.original_filename)}</div>
        ${l.error_message ? `<div class="muted" style="font-size:0.8rem;margin-top:0.2rem">${esc(l.error_message)}</div>` : ""}
      </td>
      <td><span class="status-chip ${l.status === "complete" ? "complete" : l.status === "failed" ? "failed" : "processing"}">${esc(l.status)}</span></td>
      <td class="mono">${fmtDate(l.created_at)}</td>
      <td class="lab-actions" onclick="event.stopPropagation()">
        <a href="#review/${l.id}">Review</a>
        ${l.latest_report_id ? ` · <a href="/report.html?report_id=${l.latest_report_id}">Report</a>` : ""}
        · <a href="#" data-download-lab="${l.id}" data-download-name="${esc(l.original_filename)}">Download</a>
        · <a href="#" data-reprocess-lab="${l.id}">Re-parse</a>
        · <a href="#" class="lab-delete-link" data-delete-lab="${l.id}" data-delete-name="${esc(l.original_filename)}">Delete</a>
      </td>
    </tr>`).join("") || `<tr class="no-hover"><td colspan="5" class="muted">No lab uploads</td></tr>`;

  const sessionRows = overview.analysis_sessions.map(s => `
    <tr>
      <td>${esc(s.title)}</td>
      <td>${esc(s.analysis_type)}</td>
      <td><span class="status-chip ${s.status === "complete" ? "complete" : s.status === "failed" ? "failed" : "processing"}">${esc(s.status)}</span></td>
      <td>${fmtConfLabel(s.report_confidence)}</td>
      <td>${s.latest_report_id ? `<a href="/report.html?report_id=${s.latest_report_id}">View</a>` : "—"}</td>
    </tr>`).join("") || `<tr class="no-hover"><td colspan="5" class="muted">No analyses</td></tr>`;

  const abnormal = overview.recent_abnormal_biomarkers.map(b =>
    `<span class="biomarker-chip ${b.status === "low" || b.status === "critical_low" ? "low" : "high"}">
      <span>${esc(b.biomarker_name)}</span>
      <span class="mono">${b.value} ${esc(b.unit || "")}</span>
      <span class="status-chip ${b.status.includes("low") ? "review" : "review"}" style="font-size:0.6rem">${esc(b.status).toUpperCase()}</span>
    </span>`
  ).join("") || `<span class="muted">No abnormal markers in recent labs</span>`;

  const systems = overview.top_priorities.length
    ? overview.top_priorities.map(p => `<span class="system-tag">${esc(p)}</span>`).join("")
    : `<span class="muted">Run an analysis to map biological systems</span>`;

  const primaryFindingText = overview.top_priorities[0] || (overview.latest_report_id ? "Analysis available" : "No analysis yet");
  const reviewCount = overview.lab_reports.filter(l => l.status === "complete" && !l.latest_report_id).length;

  let sectionBody = "";
  if (section === "overview") {
    sectionBody = `
      <div class="snapshot-grid">
        <div class="app-card snapshot-card">
          <h3>Primary findings</h3>
          <div class="finding">${esc(primaryFindingText)}</div>
          ${overview.latest_report_confidence != null ? `<span class="confidence-label">Analysis confidence: ${fmtConfLabel(overview.latest_report_confidence)}</span>` : ""}
        </div>
        <div class="app-card snapshot-card">
          <h3>Key biomarkers</h3>
          <div>${abnormal}</div>
        </div>
        <div class="app-card snapshot-card">
          <h3>Biological systems</h3>
          <div>${systems}</div>
        </div>
        <div class="app-card snapshot-card">
          <h3>Safety / review</h3>
          <div class="finding" style="font-size:0.95rem">${reviewCount ? `${reviewCount} item(s) require review` : "No review flags"}</div>
        </div>
      </div>
      <div class="reasoning-panel">
        <div class="app-card">
          <h3 style="margin:0 0 0.75rem;font-size:0.95rem">Biological snapshot</h3>
          <p class="muted" style="margin:0 0 0.5rem">Progressive disclosure: pattern → biomarkers → systems → evidence.</p>
          <p style="margin:0.5rem 0 0"><strong>Why?</strong> <span class="muted">${overview.recent_abnormal_biomarkers.length ? "Abnormal markers and pathway context from latest labs." : "Upload labs to begin reasoning."}</span></p>
          ${overview.latest_report_id ? `<p style="margin-top:0.75rem"><a class="app-btn app-btn-primary" href="/report.html?report_id=${overview.latest_report_id}">Open full report</a></p>` : ""}
        </div>
        <div class="app-card" id="workspace-test-plan">
          <h3 style="margin:0 0 0.5rem;font-size:0.95rem">Recommended by Discovery</h3>
          <p class="muted">These stay in this portal. Analyze them with the existing lab engine.</p>
          <div id="test-plan-mount"><p class="muted">Loading…</p></div>
        </div>
        <div class="app-card" id="workspace-longitudinal-snapshot">
          <h3 style="margin:0 0 0.5rem;font-size:0.95rem">Longitudinal memory</h3>
          <p class="muted">Built from existing labs and cases — not authored prose, and not a diagnosis.</p>
          <div id="snapshot-mount"><p class="muted">Loading…</p></div>
        </div>
        <div class="reasoning-graph-panel" id="overview-graph-shell" style="${overview.latest_report_id ? "" : "display:none"}">
          <h3>Reasoning preview</h3>
          <div class="reasoning-graph-layout">
            <div class="reasoning-graph-mount" id="overview-graph-mount"></div>
            <div class="reasoning-graph-detail" data-graph-detail>Biological relationships from the latest analysis.</div>
          </div>
        </div>
      </div>`;
    window._pendingOverviewReportId = overview.latest_report_id || null;
  } else if (section === "labs") {
    if (!overview.lab_reports.length) {
      sectionBody = `<div class="app-card empty-state">
        <svg class="empty-graph" viewBox="0 0 120 80" aria-hidden="true"><circle cx="40" cy="40" r="10" stroke="#2e7d57" fill="none"/><circle cx="80" cy="40" r="10" stroke="#6978d8" fill="none"/><line x1="50" y1="40" x2="70" y2="40" stroke="#dde1db"/></svg>
        <h3>No biological data yet</h3>
        <p>Upload a laboratory report to begin building this patient's biological profile.</p>
        <a class="app-btn app-btn-primary" href="#upload?patient=${patientId}">Upload labs</a>
      </div>`;
    } else {
      sectionBody = `
        <div class="lab-manage-bar app-card" style="margin-bottom:0.85rem;padding:0.85rem 1rem;display:flex;flex-wrap:wrap;gap:0.65rem;align-items:center;justify-content:space-between">
          <div class="muted" style="font-size:0.9rem">
            <strong style="color:inherit">${overview.lab_reports.length}</strong> lab file(s).
            Select rows to delete in bulk, or use actions on each file.
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center">
            <label class="muted" style="font-size:0.85rem;display:flex;align-items:center;gap:0.35rem;cursor:pointer">
              <input type="checkbox" id="lab-select-all" aria-label="Select all labs"> Select all
            </label>
            <button type="button" class="app-btn" id="lab-delete-selected" disabled>Delete selected</button>
            <a class="app-btn app-btn-primary" href="#upload?patient=${patientId}">Upload labs</a>
          </div>
        </div>
        <p id="lab-manage-status" class="muted" style="margin:0 0 0.65rem;min-height:1.2em"></p>
        <div class="data-table-wrap">
          <table class="data-table lab-manage-table">
            <thead>
              <tr>
                <th style="width:2.5rem"></th>
                <th>File</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>${labRows}</tbody>
          </table>
        </div>`;
    }
  } else if (section === "analyses") {
    sectionBody = await buildAnalysisWorkspace(patientId, overview, sessionRows);
  } else if (section === "context") {
    sectionBody = renderPatientContextForm(patientId, overview);
  }

  document.getElementById("app-main").innerHTML = `
    <div class="patient-header">
      <h1>${esc(overview.display_name)}</h1>
      <div class="patient-meta">
        ${sexAge ? `<span>${esc(sexAge)}</span>` : ""}
        <span><span class="mono">${overview.lab_reports.length}</span> lab reports</span>
        <span>Last updated <span class="mono">${overview.lab_reports[0] ? relTime(overview.lab_reports[0].created_at) : fmtDate(overview.created_at)}</span></span>
      </div>
      <div class="page-header-actions" style="margin-top:0.85rem">
        <a class="app-btn app-btn-primary" href="#upload?patient=${patientId}">Upload labs</a>
        <a class="app-btn" href="#analysis?patient=${patientId}">Run analysis</a>
        ${overview.latest_report_id ? `<a class="app-btn" href="/report.html?report_id=${overview.latest_report_id}">Generate report</a>` : ""}
      </div>
    </div>
    <nav class="patient-tabs" aria-label="Patient sections">
      ${tabs.map(([id, label]) => `<a class="patient-tab ${section === id ? "active" : ""}" href="#patient/${patientId}${id === "overview" ? "" : "/" + id}">${label}</a>`).join("")}
      ${overview.latest_report_id ? `<a class="patient-tab" href="/report.html?report_id=${overview.latest_report_id}">Recommendations</a><a class="patient-tab" href="/report.html?report_id=${overview.latest_report_id}#research-appendix">Evidence</a>` : ""}
    </nav>
    ${sectionBody}`;
  wireTableRows();
  wireLabDownloadLinks();
  if (section === "overview") {
    fillTestPlanMount(patientId);
    fillSnapshotMount(patientId);
  }
  if (section === "labs") wireLabManage(patientId);
  if (window._pendingAnalysisReport) {
    mountAnalysisGraph(window._pendingAnalysisReport);
    window._pendingAnalysisReport = null;
  }
  if (window._pendingOverviewReportId) {
    api(`/api/v1/reports/${window._pendingOverviewReportId}`).then(report => {
      const RG = window.HerbaGraphReasoningGraph;
      if (RG) RG.mount(document.getElementById("overview-graph-mount"), RG.buildFromReport(report));
    }).catch(() => {});
    window._pendingOverviewReportId = null;
  }
}

function renderPatientContextForm(patientId, overview) {
  const existingHtml = Object.entries(overview.context_summary || {}).map(([k, items]) =>
    `<div style="margin-bottom:0.65rem"><strong style="font-size:0.82rem;text-transform:capitalize">${esc(k.replace(/_/g, " "))}</strong><br>${items.map(i => `<span class="system-tag">${esc(i)}</span>`).join("")}</div>`
  ).join("") || `<p class="muted">No context items yet.</p>`;
  return `
    <div class="app-card"><h3 style="margin:0 0 0.75rem;font-size:1rem">Current context</h3>${existingHtml}</div>
    <div class="app-card" id="patient-condition-card">
      <h3 style="margin:0 0 0.35rem;font-size:1rem">Conditions</h3>
      <p class="muted" style="margin:0 0 0.75rem;font-size:0.85rem">Toggle conditions for this patient. Used for safety checks and condition-aligned report lanes (separate from lab priorities).</p>
      <div id="patient-condition-matrix-mount"><p class="muted">Loading condition library…</p></div>
      <button class="app-btn app-btn-primary" id="save-patient-conditions-btn" style="margin-top:0.75rem">Save conditions</button>
      <p id="patient-cond-status" class="muted" style="margin-top:0.5rem"></p>
    </div>
    <div class="app-card"><h3 style="margin:0 0 0.75rem;font-size:1rem">Add other context</h3>
      <div class="form-grid-3">
        <div class="form-row"><label>Type</label>
          <select id="ctx-type">
            <option value="medication">Medication</option>
            <option value="supplement">Supplement</option>
            <option value="allergy">Allergy</option>
            <option value="diet_pattern">Diet pattern</option>
            <option value="goal">Goal</option>
            <option value="note">Note</option>
            <option value="condition">Condition (custom)</option>
          </select>
        </div>
        <div class="form-row"><label>Name</label><input id="ctx-name" placeholder="Metformin"></div>
        <div class="form-row"><label>Value (optional)</label><input id="ctx-value" placeholder="500mg daily"></div>
      </div>
      <button class="app-btn app-btn-primary" id="add-ctx-btn">Add</button>
      <p id="ctx-error" class="error"></p>
    </div>`;
}

async function wirePatientContext(patientId) {
  const btn = document.getElementById("add-ctx-btn");
  if (btn) {
    btn.onclick = async () => {
      try {
        await api(`/api/v1/patients/${patientId}/context`, "POST", {
          context_type: document.getElementById("ctx-type").value,
          name: document.getElementById("ctx-name").value.trim(),
          value: document.getElementById("ctx-value").value.trim() || null,
        });
        render();
      } catch (e) {
        document.getElementById("ctx-error").textContent = e.message;
      }
    };
  }

  const mount = document.getElementById("patient-condition-matrix-mount");
  const saveBtn = document.getElementById("save-patient-conditions-btn");
  if (!mount || !saveBtn) return;

  try {
    const [library, ctxItems] = await Promise.all([
      loadConditionLibrary(),
      api(`/api/v1/patients/${patientId}/context`),
    ]);
    const activeConditions = (ctxItems || [])
      .filter((i) => i.context_type === "condition" && i.active !== false)
      .map((i) => i.name);
    mount.innerHTML = library.length
      ? renderConditionMatrixHtml(library, activeConditions, { idPrefix: "pt" })
      : `<p class="muted">Condition library unavailable. Use “Add other context” with type Condition.</p>`;
    if (library.length) wireConditionMatrix("pt");

    saveBtn.onclick = async () => {
      const status = document.getElementById("patient-cond-status");
      try {
        const conditions = selectedConditionLabelsFromDom(document.getElementById("patient-condition-card") || document);
        await api(`/api/v1/patients/${patientId}/conditions`, "PUT", { conditions });
        if (status) status.textContent = `Saved ${conditions.length} condition(s).`;
        // refresh summary chips without full navigation if possible
        setTimeout(() => render(), 400);
      } catch (e) {
        if (status) {
          status.textContent = e.message || "Save failed";
          status.className = "error";
        }
      }
    };
  } catch (e) {
    mount.innerHTML = `<p class="error">${esc(e.message || "Could not load conditions")}</p>`;
  }
}

async function renderReports(requestedPatientId) {
  const dash = await api("/api/v1/workspace/dashboard");
  const { patientId, patients } = await resolveActivePatientId(requestedPatientId);
  const clinician = isClinicianWorkspace();
  const reports = (dash.recent_reports || []).filter((r) => !clinician || !patientId || r.patient_id === patientId);
  const rows = reports.map(r => `
    <tr data-href="/report.html?report_id=${r.id}">
      ${clinician ? `<td>${esc(r.patient_display_name || "—")}</td>` : ""}
      <td>${esc(primaryFinding(r.title))}</td>
      <td><span class="muted">—</span></td>
      <td><span class="status-chip ready">${fmtConfLabel(r.overall_confidence)}</span></td>
      <td class="mono">${fmtDate(r.created_at)}</td>
      <td><a href="/report.html?report_id=${r.id}">View report</a></td>
    </tr>`).join("") || `<tr class="no-hover"><td colspan="${clinician ? 6 : 5}" class="muted">No reports yet for ${clinician ? "this patient" : "you"}.</td></tr>`;
  document.getElementById("app-main").innerHTML = `
    ${pageHeader("Reports", clinician ? "Analyses for the selected patient." : "Your structured analyses.")}
    ${renderPatientScopeBar(patients, patientId, "reports")}
    <div class="data-table-wrap"><table class="data-table"><thead><tr>
      ${clinician ? "<th>Patient</th>" : ""}<th>Primary finding</th><th>Systems</th><th>Confidence</th><th>Created</th><th></th>
    </tr></thead><tbody>${rows}</tbody></table></div>`;
  wirePatientScopeSelect("reports");
  wireTableRows();
}

async function renderEvidence(requestedPatientId) {
  const dash = await api("/api/v1/workspace/dashboard");
  const { patientId, patients } = await resolveActivePatientId(requestedPatientId);
  const clinician = isClinicianWorkspace();
  const reports = (dash.recent_reports || []).filter((r) => !patientId || r.patient_id === patientId);
  const latest = reports[0];
  const subtitle = clinician
    ? "Evidence is attached to a specific patient's report — never the last report in the clinic."
    : "Open your report to see why a recommendation is 78%: evidence, match, and missing data.";
  const list = reports.map((r) => `
    <tr data-href="/report.html?report_id=${r.id}#research-appendix">
      ${clinician ? `<td>${esc(r.patient_display_name || "—")}</td>` : ""}
      <td>${esc(primaryFinding(r.title))}</td>
      <td class="mono">${fmtDate(r.created_at)}</td>
      <td><a href="/report.html?report_id=${r.id}#research-appendix">Open evidence</a></td>
    </tr>`).join("") || `<tr class="no-hover"><td colspan="${clinician ? 4 : 3}" class="muted">${clinician && !patientId ? "Select a patient to see their evidence." : "No reports yet."}</td></tr>`;

  document.getElementById("app-main").innerHTML = `
    ${pageHeader("Evidence", subtitle)}
    ${renderPatientScopeBar(patients, patientId, "evidence")}
    <div class="app-card">
      <p class="muted" style="margin:0 0 1rem">${clinician
        ? "Each row is one patient's report. Confidence decomposition lives on that report, not on a shared clinic score."
        : "Your evidence profile is personal. It is not mixed with anyone else's labs."}</p>
      ${latest ? `<a class="app-btn app-btn-primary" href="/report.html?report_id=${latest.id}#research-appendix">Open ${clinician ? "this patient's" : "your"} latest evidence</a>` : `<a class="app-btn" href="/report.html?demo=1">View sample report</a>`}
    </div>
    <div class="data-table-wrap" style="margin-top:1rem"><table class="data-table"><thead><tr>
      ${clinician ? "<th>Patient</th>" : ""}<th>Report</th><th>Date</th><th></th>
    </tr></thead><tbody>${list}</tbody></table></div>`;
  wirePatientScopeSelect("evidence");
  wireTableRows();
}

async function ensurePatients() {
  let patients = await api("/api/v1/patients");
  if (!patients.length) {
    await api("/api/v1/workspace/dashboard");
    patients = await api("/api/v1/patients");
  }
  return patients;
}

const UPLOAD_STAGES = ["Uploaded", "Extracting biomarkers", "Normalizing ranges", "Mapping systems", "Preparing analysis"];

function renderUploadStages(activeIdx) {
  return UPLOAD_STAGES.map((label, i) => {
    let cls = "process-stage";
    let icon = "○";
    if (i < activeIdx) { cls += " done"; icon = "●"; }
    else if (i === activeIdx) { cls += " active"; icon = "◌"; }
    return `<div class="${cls}"><span class="stage-icon">${icon}</span>${label}</div>`;
  }).join("");
}

async function renderUpload(preselectedPatient) {
  const { patientId, patients } = await resolveActivePatientId(preselectedPatient);
  const clinician = isClinicianWorkspace();
  const opts = patients.map(p => `<option value="${p.id}" ${p.id === patientId ? "selected" : ""}>${esc(p.display_name)}</option>`).join("");
  document.getElementById("app-main").innerHTML = `
    ${pageHeader("Upload laboratory reports", clinician ? "Files attach to the selected patient." : "These labs stay on your profile.")}
    ${renderPatientScopeBar(patients, patientId, "upload")}
    <div class="app-card">
      <div class="form-row" ${clinician ? "" : "hidden"}><label>Patient</label><select id="upload-patient">${opts}</select></div>
      <div class="upload-zone" id="upload-zone">
        <h3>Drag and drop PDF files</h3>
        <p>or <label style="color:var(--app-green);cursor:pointer;text-decoration:underline"><input id="upload-files" type="file" multiple accept=".pdf,.txt,.csv,.png,.jpg,.jpeg" style="display:none">browse files</label></p>
        <p style="margin-top:0.5rem;font-size:0.78rem">Supported: PDF, TXT, CSV, images · Multiple reports</p>
      </div>
      <div class="process-stages" id="upload-stages" style="display:none"></div>
      <p id="upload-status" class="muted" style="margin-top:1rem"></p>
    </div>`;
  wirePatientScopeSelect("upload");

  const fileInput = document.getElementById("upload-files");
  const zone = document.getElementById("upload-zone");
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.style.borderColor = "var(--app-green)"; });
  zone.addEventListener("dragleave", () => { zone.style.borderColor = ""; });
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.style.borderColor = "";
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      startUpload();
    }
  });
  fileInput.addEventListener("change", () => { if (fileInput.files.length) startUpload(); });

  async function uploadLabFile(file, patientId) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("patient_id", patientId);
    let resp = await fetch(API + "/api/v1/labs/upload", { method: "POST", headers: { Authorization: `Bearer ${window.hgToken}` }, body: fd });
    if (resp.status === 401 && window.hgRefreshToken) {
      await Auth.refreshTokens();
      resp = await fetch(API + "/api/v1/labs/upload", { method: "POST", headers: { Authorization: `Bearer ${window.hgToken}` }, body: fd });
    }
    if (!resp.ok) {
      const text = await resp.text();
      try { throw new Error(JSON.parse(text).detail || text); } catch (e) { if (e.message) throw e; throw new Error(text); }
    }
    return resp.json();
  }

  async function startUpload() {
    const files = fileInput.files;
    const status = document.getElementById("upload-status");
    const selectedPatient = (document.getElementById("upload-patient") && document.getElementById("upload-patient").value) || patientId;
    if (!files.length) return;
    if (!selectedPatient) {
      status.textContent = "Select a patient first.";
      return;
    }
    rememberPatientId(selectedPatient);
    const stagesEl = document.getElementById("upload-stages");
    stagesEl.style.display = "flex";
    status.textContent = "";
    status.className = "muted";
    try {
      for (const file of files) {
        stagesEl.innerHTML = renderUploadStages(0);
        const body = await uploadLabFile(file, selectedPatient);
        for (let s = 1; s <= 3; s++) { stagesEl.innerHTML = renderUploadStages(s); await new Promise(r => setTimeout(r, 400)); }
        status.textContent = `Uploaded ${file.name}. Parsing…`;
        await pollLab(body.lab_report_id, status, stagesEl);
      }
      stagesEl.innerHTML = renderUploadStages(UPLOAD_STAGES.length);
      status.textContent = "Upload complete. Review biomarkers or run analysis.";
      location.hash = `#patient/${selectedPatient}/labs`;
      render();
    } catch (e) {
      status.textContent = e.message;
      status.className = "error";
    }
  }
}

async function pollLab(labId, el, stagesEl) {
  for (let i = 0; i < 120; i++) {
    const lab = await api(`/api/v1/labs/${labId}`);
    if (lab.status === "complete") {
      if (stagesEl) stagesEl.innerHTML = renderUploadStages(UPLOAD_STAGES.length);
      return lab;
    }
    if (lab.status === "failed") throw new Error(lab.error_message || "We could not confidently extract biomarkers from this report. Try uploading a clearer file or review extracted data.");
    const stageMap = { uploaded: 1, parsing: 2, normalizing: 3 };
    const idx = stageMap[lab.processing_stage] || stageMap[lab.status] || 2;
    if (stagesEl) stagesEl.innerHTML = renderUploadStages(idx);
    el.textContent = `${lab.processing_stage || lab.status}…`;
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error("Parse timed out. The report may still be processing. Check the patient labs tab shortly.");
}

const ANALYSIS_PIPELINE = ["Reading biomarkers", "Normalizing laboratory ranges", "Mapping biological systems", "Evaluating pathway relevance", "Reviewing evidence"];

function renderAnalysisPipeline(activeIdx) {
  return ANALYSIS_PIPELINE.map((label, i) => {
    let cls = "process-stage";
    let icon = "○";
    if (i < activeIdx) { cls += " done"; icon = "●"; }
    else if (i === activeIdx) { cls += " active"; icon = "◌"; }
    return `<div class="${cls}"><span class="stage-icon">${icon}</span>${label}</div>`;
  }).join("");
}

async function renderBiomarkerReview(labId) {
  const lab = await api(`/api/v1/labs/${labId}`);
  const rows = (lab.lab_results || []).map(r => `
    <tr>
      <td>${esc(r.biomarker_name)}</td>
      <td class="mono">${r.value}</td>
      <td class="mono">${esc(r.unit || "")}</td>
      <td class="mono">${r.reference_range_low ?? "—"} – ${r.reference_range_high ?? "—"}</td>
      <td><span class="status-chip ${r.status === "normal" ? "ready" : "review"}">${esc(r.status)}</span></td>
    </tr>`).join("") || `<tr class="no-hover"><td colspan="5" class="muted">No biomarkers extracted</td></tr>`;
  document.getElementById("app-main").innerHTML = `
    ${pageHeader("Biomarker review", `${esc(lab.original_filename)} · ${esc(lab.status)}`)}
    <div class="app-card">
      <p class="muted">Review parsed values before running analysis.</p>
      <div class="data-table-wrap" style="margin-top:0.75rem"><table class="data-table"><thead><tr><th>Biomarker</th><th>Value</th><th>Unit</th><th>Reference</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="page-header-actions" style="margin-top:1rem">
        ${lab.status === "complete" ? `<button class="app-btn app-btn-primary" id="gen-report-btn">Generate single-report analysis</button>` : ""}
        <button type="button" class="app-btn" id="download-lab-btn">Download original file</button>
        <a class="app-btn" href="#analysis">Multi-report analysis</a>
      </div>
      <p id="review-status" class="muted"></p>
    </div>`;
  const dlBtn = document.getElementById("download-lab-btn");
  if (dlBtn) {
    dlBtn.onclick = async () => {
      const st = document.getElementById("review-status");
      dlBtn.disabled = true;
      try {
        await downloadLabUpload(labId, lab.original_filename);
        if (st) st.textContent = "Download started.";
      } catch (err) {
        if (st) st.textContent = err.message || "Download failed";
      } finally {
        dlBtn.disabled = false;
      }
    };
  }
  const genBtn = document.getElementById("gen-report-btn");
  if (genBtn) {
    genBtn.onclick = async () => {
      const st = document.getElementById("review-status");
      const knowledgePath = await window.hgPickKnowledgePath({
        title: "Choose knowledge path for this analysis",
        subtitle: "Same biomarkers. Different knowledge substrate — compare legacy catalogs vs the canonical intervention graph.",
      });
      if (!knowledgePath) return;
      st.textContent = `Starting analysis (${knowledgePath})…`;
      try {
        await api(`/api/v1/reports/generate/${labId}`, "POST", { knowledge_path: knowledgePath });
        for (let i = 0; i < 180; i++) {
          const refreshed = await api(`/api/v1/labs/${labId}`);
          if (refreshed.report_stage === "complete" && refreshed.latest_report_id) {
            location.href = `/report.html?report_id=${refreshed.latest_report_id}`;
            return;
          }
          if (refreshed.report_stage === "failed") throw new Error(refreshed.report_error_message || "Analysis failed");
          st.textContent = `Generating (${String(refreshed.report_stage).replace(/_/g, " ")})…`;
          await new Promise(r => setTimeout(r, 2500));
        }
        throw new Error("Report generation timed out");
      } catch (e) {
        st.textContent = e.message;
        st.className = "error";
      }
    };
  }
}

async function renderAnalysisBuilder(preselectedPatient) {
  const { patientId, patients } = await resolveActivePatientId(preselectedPatient);
  const clinician = isClinicianWorkspace();
  const labs = patientId ? await api(`/api/v1/labs?patient_id=${patientId}`) : [];
  const checkboxes = labs.filter(l => l.status === "complete").map(l => `
    <label style="display:block;margin:0.35rem 0;font-size:0.88rem">
      <input type="checkbox" class="analysis-lab" value="${l.id}" checked> ${esc(l.original_filename)}
    </label>`).join("") || `<p class="muted">Upload at least one parsed lab report ${clinician ? "for this patient" : "to your profile"}.</p>`;
  const opts = patients.map(p => `<option value="${p.id}" ${p.id === patientId ? "selected" : ""}>${esc(p.display_name)}</option>`).join("");
  document.getElementById("app-main").innerHTML = `
    ${pageHeader("Analysis builder", clinician ? "Merge this patient's labs into one reasoning run." : "Merge your labs into one reasoning run.")}
    ${renderPatientScopeBar(patients, patientId, "analysis")}
    <div class="app-card">
      <div class="form-grid-2">
        <div class="form-row" ${clinician ? "" : "hidden"}><label>Patient</label><select id="analysis-patient">${opts}</select></div>
        <div class="form-row"><label>Analysis type</label>
          <select id="analysis-type">
            <option value="multi_report_snapshot">Current snapshot</option>
            <option value="longitudinal_comparison">Compare to prior</option>
            <option value="single_report">Single report</option>
          </select>
        </div>
      </div>
      <div class="form-row"><label>Select lab reports</label><div id="analysis-lab-list">${checkboxes}</div></div>
      <button class="app-btn app-btn-primary" id="run-analysis-btn">Run integrated analysis</button>
      <div class="analysis-pipeline" id="analysis-pipeline" style="display:none"></div>
      <p id="analysis-status" class="muted" style="margin-top:0.75rem"></p>
    </div>`;
  wirePatientScopeSelect("analysis");
  const analysisPatient = document.getElementById("analysis-patient");
  if (analysisPatient) {
    analysisPatient.onchange = () => {
      rememberPatientId(analysisPatient.value);
      location.hash = `#analysis?patient=${analysisPatient.value}`;
      render();
    };
  }
  document.getElementById("run-analysis-btn").onclick = async () => {
    const st = document.getElementById("analysis-status");
    const pipeline = document.getElementById("analysis-pipeline");
    const selected = [...document.querySelectorAll(".analysis-lab:checked")].map(el => el.value);
    if (selected.length < 1) { st.textContent = "Select at least one lab report."; return; }
    const knowledgePath = await window.hgPickKnowledgePath({
      title: "Choose knowledge path for integrated analysis",
      subtitle: "Pick legacy catalogs or the canonical graph before merging reports into one reasoning run.",
    });
    if (!knowledgePath) return;
    st.textContent = `Creating session (${knowledgePath})…`;
    pipeline.style.display = "block";
    pipeline.innerHTML = renderAnalysisPipeline(0);
    try {
      const session = await api("/api/v1/analysis-sessions", "POST", {
        title: "Integrated Lab Analysis",
        patient_id: (document.getElementById("analysis-patient") && document.getElementById("analysis-patient").value) || patientId,
        analysis_type: document.getElementById("analysis-type").value,
      });
      await api(`/api/v1/analysis-sessions/${session.id}/link-labs`, "POST", { lab_report_ids: selected });
      await api(`/api/v1/analysis-sessions/${session.id}/run`, "POST", { knowledge_path: knowledgePath });
      for (let i = 0; i < 180; i++) {
        const s = await api(`/api/v1/analysis-sessions/${session.id}`);
        if (s.status === "complete" && s.latest_report_id) {
          location.href = `/report.html?report_id=${s.latest_report_id}&session_id=${session.id}`;
          return;
        }
        if (s.status === "failed") throw new Error(s.error_message || "Analysis failed");
        const stageIdx = s.status === "analyzing" ? 3 : 1;
        pipeline.innerHTML = renderAnalysisPipeline(stageIdx);
        if (s.status === "analyzing" && s.anchor_lab_report_id) {
          const anchor = await api(`/api/v1/labs/${s.anchor_lab_report_id}`);
          st.textContent = `${String(anchor.report_stage || s.status).replace(/_/g, " ")}…`;
        } else {
          st.textContent = `${s.status}…`;
        }
        await new Promise(r => setTimeout(r, 2500));
      }
    } catch (e) {
      st.textContent = e.message;
      st.className = "error";
    }
  };
}


/* ── Condition matrix (preloaded library + Other) ───────────────── */
let _conditionLibraryCache = null;

async function loadConditionLibrary() {
  if (_conditionLibraryCache) return _conditionLibraryCache;
  const rows = await api("/api/v1/safety/conditions");
  _conditionLibraryCache = Array.isArray(rows) ? rows : [];
  return _conditionLibraryCache;
}

function groupConditionsByCategory(library) {
  const grouped = {};
  for (const row of library) {
    const cat = row.category || "General";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(row);
  }
  return grouped;
}

function selectedConditionLabelsFromDom(root = document) {
  const labels = [];
  root.querySelectorAll(".condition-chip input[type=checkbox]:checked").forEach((el) => {
    const label = el.getAttribute("data-label") || el.value;
    if (label) labels.push(label);
  });
  const otherEl = root.querySelector("#condition-other");
  if (otherEl && otherEl.value.trim()) {
    otherEl.value.split(",").map((s) => s.trim()).filter(Boolean).forEach((s) => labels.push(s));
  }
  // de-dupe case-insensitive
  const seen = new Set();
  const out = [];
  for (const l of labels) {
    const k = l.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(l);
  }
  return out;
}

function renderConditionMatrixHtml(library, selectedLabels, { otherText = "", idPrefix = "cond" } = {}) {
  const selected = new Set((selectedLabels || []).map((s) => String(s).trim().toLowerCase()));
  const libraryLabels = new Set(library.map((r) => (r.label || "").toLowerCase()));
  // free-text others = selected not in library
  const others = (selectedLabels || []).filter((s) => !libraryLabels.has(String(s).trim().toLowerCase()));
  const otherVal = otherText || others.join(", ");
  const grouped = groupConditionsByCategory(library);
  let html = `<div class="condition-matrix" id="${idPrefix}-matrix">`;
  html += `<div class="condition-matrix-toolbar">
    <input type="search" class="condition-matrix-search" id="${idPrefix}-search" placeholder="Search conditions…" autocomplete="off">
    <span class="condition-matrix-count" id="${idPrefix}-count"></span>
  </div>`;
  for (const [cat, rows] of Object.entries(grouped)) {
    html += `<div class="condition-matrix-category" data-category-block>${esc(cat)}</div>`;
    html += `<div class="condition-matrix-grid" data-category-grid="${esc(cat)}">`;
    for (const row of rows) {
      const label = row.label || row.key;
      const checked = selected.has(String(label).toLowerCase()) || selected.has(String(row.key || "").toLowerCase())
        || (row.aliases || []).some((a) => selected.has(String(a).toLowerCase()));
      html += `<label class="condition-chip" data-search="${esc((label + " " + (row.aliases || []).join(" ")).toLowerCase())}">
        <input type="checkbox" value="${esc(row.key)}" data-label="${esc(label)}" ${checked ? "checked" : ""}>
        <span>${esc(label)}</span>
      </label>`;
    }
    html += `</div>`;
  }
  html += `<div class="condition-other-row">
    <label for="condition-other">Other conditions (comma-separated)</label>
    <input type="text" id="condition-other" placeholder="e.g. Ehlers-Danlos, longstanding tinnitus" value="${esc(otherVal)}">
    <p class="muted" style="margin:0.35rem 0 0;font-size:0.8rem">Toggles use the clinical library for safety and condition-aligned report lanes. Use Other for anything not listed.</p>
  </div>`;
  html += `</div>`;
  return html;
}

function wireConditionMatrix(idPrefix = "cond") {
  const search = document.getElementById(`${idPrefix}-search`);
  const countEl = document.getElementById(`${idPrefix}-count`);
  const matrix = document.getElementById(`${idPrefix}-matrix`);
  if (!matrix) return;
  const updateCount = () => {
    if (!countEl) return;
    const n = matrix.querySelectorAll(".condition-chip input:checked").length;
    countEl.textContent = n ? `${n} selected` : "None selected";
  };
  const filter = () => {
    const q = (search && search.value || "").trim().toLowerCase();
    matrix.querySelectorAll(".condition-chip").forEach((chip) => {
      const hay = chip.getAttribute("data-search") || "";
      chip.style.display = !q || hay.includes(q) ? "" : "none";
    });
    // hide empty category headers
    matrix.querySelectorAll("[data-category-grid]").forEach((grid) => {
      const any = Array.from(grid.querySelectorAll(".condition-chip")).some((c) => c.style.display !== "none");
      const header = grid.previousElementSibling;
      if (header && header.classList.contains("condition-matrix-category")) {
        header.style.display = any ? "" : "none";
      }
      grid.style.display = any ? "" : "none";
    });
  };
  if (search) search.addEventListener("input", filter);
  matrix.addEventListener("change", updateCount);
  updateCount();
}

async function renderSettings() {
  const profile = await api("/api/v1/auth/profile");
  let library = [];
  try {
    library = await loadConditionLibrary();
  } catch (e) {
    library = [];
  }
  const matrixHtml = library.length
    ? renderConditionMatrixHtml(library, profile.known_conditions || [], { idPrefix: "hp" })
    : `<div class="form-row"><label>Conditions (comma-separated)</label><input id="hp-conds" value="${esc((profile.known_conditions || []).join(", "))}"></div>`;
  document.getElementById("app-main").innerHTML = `
    ${pageHeader("Settings", "Health profile informs safety checks, condition-aligned lanes, and reasoning context.")}
    <div class="app-card" style="max-width:920px">
      <div class="form-row"><label>Age range</label><input id="hp-age" value="${esc(profile.age_range || "")}"></div>
      <div class="form-row"><label>Biological sex</label><input id="hp-sex" value="${esc(profile.biological_sex || "")}"></div>
      <div class="form-row"><label>Medications (comma-separated)</label><input id="hp-meds" value="${esc((profile.current_medications || []).join(", "))}"></div>
      <div class="form-row"><label>Supplements (comma-separated)</label><input id="hp-sups" value="${esc((profile.current_supplements || []).join(", "))}"></div>
      <div class="form-row" style="margin-top:1rem">
        <label style="display:block;font-weight:600;margin-bottom:0.35rem">Conditions</label>
        <p class="muted" style="margin:0 0 0.5rem;font-size:0.85rem">Toggle common conditions for safety and report context. Search to filter the matrix.</p>
        ${matrixHtml}
      </div>
      <button class="app-btn app-btn-primary" id="save-profile-btn">Save profile</button>
      <p id="settings-status" class="muted" style="margin-top:0.5rem"></p>
    </div>`;
  if (library.length) wireConditionMatrix("hp");
  document.getElementById("save-profile-btn").onclick = async () => {
    const split = s => s.split(",").map(x => x.trim()).filter(Boolean);
    let known_conditions;
    if (library.length) {
      known_conditions = selectedConditionLabelsFromDom(document.getElementById("app-main"));
    } else {
      known_conditions = split(document.getElementById("hp-conds").value);
    }
    await api("/api/v1/auth/profile", "PUT", {
      age_range: document.getElementById("hp-age").value || null,
      biological_sex: document.getElementById("hp-sex").value || null,
      current_medications: split(document.getElementById("hp-meds").value),
      current_supplements: split(document.getElementById("hp-sups").value),
      known_conditions,
    });
    document.getElementById("settings-status").textContent = "Saved.";
  };
}

function wireTableRows() {
  document.querySelectorAll(".data-table tbody tr[data-href]").forEach(row => {
    row.addEventListener("click", e => {
      if (e.target.closest("a")) return;
      const href = row.dataset.href;
      if (href.startsWith("/")) location.href = href;
      else location.hash = href;
    });
  });
}

function wireLabDownloadLinks() {
  document.querySelectorAll("[data-download-lab]").forEach(el => {
    el.addEventListener("click", async e => {
      e.preventDefault();
      e.stopPropagation();
      const id = el.getAttribute("data-download-lab");
      const name = el.getAttribute("data-download-name") || "lab-upload";
      const prev = el.textContent;
      el.textContent = "Downloading…";
      try {
        await downloadLabUpload(id, name);
      } catch (err) {
        alert(err.message || "Download failed");
      } finally {
        el.textContent = prev || "Download";
      }
    });
  });
}

function wireLabManage(patientId) {
  const statusEl = document.getElementById("lab-manage-status");
  const selectAll = document.getElementById("lab-select-all");
  const deleteSelectedBtn = document.getElementById("lab-delete-selected");
  const boxes = () => [...document.querySelectorAll(".lab-select-cb")];

  function updateBulkState() {
    const selected = boxes().filter(b => b.checked);
    if (deleteSelectedBtn) {
      deleteSelectedBtn.disabled = selected.length === 0;
      deleteSelectedBtn.textContent =
        selected.length > 0 ? `Delete selected (${selected.length})` : "Delete selected";
    }
    if (selectAll) {
      const all = boxes();
      selectAll.checked = all.length > 0 && selected.length === all.length;
      selectAll.indeterminate = selected.length > 0 && selected.length < all.length;
    }
  }

  boxes().forEach(b => b.addEventListener("change", updateBulkState));
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      boxes().forEach(b => { b.checked = selectAll.checked; });
      updateBulkState();
    });
  }

  async function deleteLabs(ids, names) {
    if (!ids.length) return;
    const label = ids.length === 1
      ? `Delete “${names[0] || "this lab"}”? Related reports linked only to this file will also be removed. This cannot be undone.`
      : `Delete ${ids.length} lab files? Related reports linked only to these files will also be removed. This cannot be undone.`;
    if (!confirm(label)) return;
    if (statusEl) statusEl.textContent = `Deleting ${ids.length} file(s)…`;
    const errors = [];
    for (let i = 0; i < ids.length; i++) {
      try {
        await api(`/api/v1/labs/${ids[i]}`, "DELETE");
      } catch (err) {
        errors.push(`${names[i] || ids[i]}: ${err.message || "failed"}`);
        console.error(err);
      }
    }
    if (errors.length) {
      alert(
        `${errors.length} of ${ids.length} could not be deleted:\n\n` +
          errors.slice(0, 3).join("\n") +
          (errors.length > 3 ? `\n…and ${errors.length - 3} more` : "")
      );
    }
    await renderPatient(patientId, "labs");
  }

  document.querySelectorAll("[data-delete-lab]").forEach(el => {
    el.addEventListener("click", async e => {
      e.preventDefault();
      e.stopPropagation();
      const id = el.getAttribute("data-delete-lab");
      const name = el.getAttribute("data-delete-name") || "lab file";
      await deleteLabs([id], [name]);
    });
  });

  document.querySelectorAll("[data-reprocess-lab]").forEach(el => {
    el.addEventListener("click", async e => {
      e.preventDefault();
      e.stopPropagation();
      const id = el.getAttribute("data-reprocess-lab");
      const prev = el.textContent;
      el.textContent = "Re-parsing…";
      try {
        const res = await api(`/api/v1/labs/${id}/reprocess`, "POST");
        if (statusEl) {
          statusEl.textContent = `Re-parsed: ${res.biomarker_count ?? "?"} biomarker(s).`;
        }
        await renderPatient(patientId, "labs");
      } catch (err) {
        alert(err.message || "Re-parse failed");
        el.textContent = prev || "Re-parse";
      }
    });
  });

  if (deleteSelectedBtn) {
    deleteSelectedBtn.addEventListener("click", async () => {
      const selected = boxes().filter(b => b.checked);
      const ids = selected.map(b => b.value);
      const names = selected.map(b => {
        const row = b.closest("tr");
        const nameEl = row && row.querySelector(".lab-file-name");
        return nameEl ? nameEl.textContent.trim() : b.value;
      });
      await deleteLabs(ids, names);
    });
  }

  updateBulkState();
}

function wireCommandSearch(dash) {
  const input = document.getElementById("workspace-search");
  if (!input) return;
  input.addEventListener("focus", () => openCommandPalette(dash || lastDashboard));
  input.addEventListener("keydown", e => { if (e.key === "Enter") openCommandPalette(dash || lastDashboard, input.value); });
}

function openCommandPalette(dash, query = "") {
  if (!dash) return;
  const existing = document.getElementById("command-palette-overlay");
  if (existing) existing.remove();
  const overlay = document.createElement("div");
  overlay.id = "command-palette-overlay";
  overlay.className = "command-palette-overlay";
  overlay.innerHTML = `<div class="command-palette" role="dialog" aria-label="Search workspace">
    <input type="search" id="palette-input" placeholder="Search patients, reports, biomarkers…" value="${esc(query)}">
    <div class="command-results" id="palette-results"></div>
  </div>`;
  document.body.appendChild(overlay);
  const inp = overlay.querySelector("#palette-input");
  const results = overlay.querySelector("#palette-results");
  const renderResults = (q) => {
    const ql = (q || "").toLowerCase();
    const items = [];
    for (const p of dash.patients) {
      if (!ql || p.display_name.toLowerCase().includes(ql)) items.push({ label: p.display_name, sub: "Patient", href: `#patient/${p.id}` });
    }
    for (const r of dash.recent_reports) {
      if (!ql || (r.patient_display_name || "").toLowerCase().includes(ql) || r.title.toLowerCase().includes(ql))
        items.push({ label: primaryFinding(r.title), sub: r.patient_display_name || "Report", href: `/report.html?report_id=${r.id}` });
    }
    results.innerHTML = items.slice(0, 8).map(it => `<a class="command-result" href="${it.href}">${esc(it.label)}<small>${esc(it.sub)}</small></a>`).join("") || `<p class="muted" style="padding:1rem">No results</p>`;
  };
  renderResults(query);
  inp.focus();
  inp.addEventListener("input", () => renderResults(inp.value));
  overlay.addEventListener("click", e => { if (e.target === overlay) overlay.remove(); });
  inp.addEventListener("keydown", e => { if (e.key === "Escape") overlay.remove(); });
}

document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault();
    openCommandPalette(lastDashboard);
  }
});

function setActiveNav(route) {
  document.querySelectorAll("[data-nav]").forEach(a => {
    a.classList.toggle("active", route.startsWith(a.dataset.nav));
  });
}

async function render() {
  try {
    if (window.__hgAuthRedirecting) return;
    // OAuth / email-confirm may land with tokens in the URL. Clean them, then always continue rendering.
    // Previously we returned early after setting #dashboard — if hash was already #dashboard,
    // hashchange never fired and the shell stayed hidden (gray screen on mobile).
    await Auth.handleAuthRedirect();
    if (!location.hash || location.hash === "#") {
      history.replaceState({}, document.title, location.pathname + location.search + "#dashboard");
    }

    const hash = location.hash.slice(1) || "dashboard";
    if (hash === "login") { redirectToLogin(); return; }
    if (!(await ensureSession())) { redirectToLogin(); return; }

    const expectedPath = window.HerbaGraphWorkspace
      ? window.HerbaGraphWorkspace.portalPath(currentUser && currentUser.role)
      : (window.HG_PORTAL_HOME || "/me.html");
    if (!location.pathname.endsWith(expectedPath)) {
      location.replace(expectedPath + location.search + (location.hash || "#dashboard"));
      return;
    }

    document.getElementById("app-shell").classList.remove("hidden");
    document.getElementById("nav-user").textContent = currentUser?.email
      ? `${currentUser.email} · ${isClinicianWorkspace() ? "Clinician" : "Personal"}`
      : "";
    document.getElementById("logout-btn").onclick = signOut;
    wireMobileNav();
    closeSidebar();

    const params = new URLSearchParams(hash.split("?")[1] || "");
    const path = hash.split("?")[0];

    if (path === "dashboard") { setActiveNav("dashboard"); await renderDashboard(); }
    else if (path === "discovery") {
      const next = new URL("/ask.html", location.origin);
      if (params.get("case")) next.searchParams.set("case", params.get("case"));
      if (params.get("patient")) next.searchParams.set("patient", params.get("patient"));
      location.replace(next.pathname + next.search);
      return;
    }
    else if (path === "patients") { setActiveNav("patients"); await renderPatients(); }
    else if (path === "reports") { setActiveNav("reports"); await renderReports(params.get("patient")); }
    else if (path === "evidence") { setActiveNav("evidence"); await renderEvidence(params.get("patient")); }
    else if (path === "upload") { setActiveNav("upload"); await renderUpload(params.get("patient")); }
    else if (path === "analysis") { setActiveNav("analysis"); await renderAnalysisBuilder(params.get("patient")); }
    else if (path === "settings") { setActiveNav("settings"); await renderSettings(); }
    else if (path.startsWith("patient/")) {
      setActiveNav("patients");
      const parts = path.split("/");
      await renderPatient(parts[1], parts[2] || "overview");
      if ((parts[2] || "overview") === "context") await wirePatientContext(parts[1]);
    }
    else if (path.startsWith("review/")) {
      setActiveNav("upload");
      await renderBiomarkerReview(path.split("/")[1]);
    }
    else { setActiveNav("dashboard"); await renderDashboard(); }
  } catch (err) {
    console.error("HerbaGraph workspace render failed:", err);
    showAppError(err);
  }
}

function redirectToLogin() {
  const next = encodeURIComponent(location.pathname + location.search + location.hash);
  location.href = `/login.html?next=${next}`;
}

window.addEventListener("hashchange", () => render());
render();
