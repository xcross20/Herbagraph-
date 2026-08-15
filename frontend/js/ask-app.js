/* Secondary Ask portal. Uses the existing Case API. Does not replace the workspace. */
(function () {
  const API = window.location.origin;
  const Auth = window.HerbaGraphAuth;
  const WS = window.HerbaGraphWorkspace;
  const EXAMPLES = [
    "For six months, my feet have burned at night. My doctor says my blood work is normal.",
    "I already have labs — take me to upload.",
    "I've been having pressure on the right side of my face for almost a year.",
    "I've been dealing with this weird pain under my right ribs for eight months.",
  ];

  function esc(s) {
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  async function api(path, method, body) {
    const headers = { "Content-Type": "application/json" };
    if (window.hgToken) headers.Authorization = `Bearer ${window.hgToken}`;
    let resp = await fetch(API + path, { method: method || "GET", headers, body: body ? JSON.stringify(body) : undefined });
    if (resp.status === 401 && window.hgRefreshToken) {
      await Auth.refreshTokens();
      headers.Authorization = `Bearer ${window.hgToken}`;
      resp = await fetch(API + path, { method: method || "GET", headers, body: body ? JSON.stringify(body) : undefined });
    }
    if (!resp.ok) {
      const raw = await resp.text();
      let detail = raw || resp.statusText;
      try {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.detail) detail = typeof parsed.detail === "string" ? parsed.detail : raw;
      } catch (_) { /* keep raw body */ }
      throw new Error(detail);
    }
    return resp.status === 204 ? null : resp.json();
  }

  async function apiStream(path, body, onEvent) {
    const headers = { "Content-Type": "application/json" };
    if (window.hgToken) headers.Authorization = `Bearer ${window.hgToken}`;
    let resp = await fetch(API + path, { method: "POST", headers, body: JSON.stringify(body) });
    if (resp.status === 401 && window.hgRefreshToken) {
      await Auth.refreshTokens();
      headers.Authorization = `Bearer ${window.hgToken}`;
      resp = await fetch(API + path, { method: "POST", headers, body: JSON.stringify(body) });
    }
    if (!resp.ok || !resp.body) {
      const raw = await resp.text();
      throw new Error(raw || resp.statusText);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buf += decoder.decode(chunk.value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        onEvent(JSON.parse(line));
      }
    }
    if (buf.trim()) onEvent(JSON.parse(buf));
  }

  function params() {
    return new URLSearchParams(location.search);
  }

  function goWorkspace(hash) {
    const home = (WS && currentUser && WS.workspaceHome(currentUser.role, { hash: hash || "#dashboard" })) || "/me.html#dashboard";
    location.href = home;
  }

  let currentUser = null;
  let currentCase = null;
  let patients = [];
  let patientId = null;
  let sending = false;

  function renderHome() {
    const clinician = WS && WS.isClinicianRole(currentUser && currentUser.role);
    document.getElementById("ask-main").innerHTML = `
      <section class="ask-home">
        <h1>Discovery Guide</h1>
        <p class="ask-lede">Tell me what's been going on. Start wherever makes sense. Labs, reports, and evidence stay in the workspace.</p>
        ${clinician ? `<p class="ask-scope">Patient <select id="ask-patient">${patients.map((p) => `<option value="${p.id}" ${p.id === patientId ? "selected" : ""}>${esc(p.display_name)}</option>`).join("") || "<option value=\"\">Add a patient in the workspace first</option>"}</select></p>` : ""}
        <form class="ask-composer" id="ask-form">
          <textarea id="ask-input" rows="3" required placeholder="Start wherever makes sense…"></textarea>
          <button type="submit">Talk to Discovery Guide</button>
        </form>
        <div class="ask-chips">
          ${EXAMPLES.map((ex, i) => `<button type="button" class="ask-chip" data-ex="${i}">${esc(i === 1 ? "I already have labs" : ex.slice(0, 42) + (ex.length > 42 ? "…" : ""))}</button>`).join("")}
        </div>
        <p class="ask-note">Not a diagnosis. The Case is the source of truth — this page is only a conversation surface.</p>
      </section>`;
    bindComposer();
    document.querySelectorAll("[data-ex]").forEach((btn) => {
      btn.onclick = async () => {
        const ex = EXAMPLES[Number(btn.getAttribute("data-ex"))];
        if (ex.includes("upload")) { goWorkspace("#upload"); return; }
        document.getElementById("ask-input").value = ex;
        await startOrContinue(ex);
      };
    });
    const sel = document.getElementById("ask-patient");
    if (sel) sel.onchange = () => { patientId = sel.value || null; };
  }

  function renderAskSafety(body) {
    const state = (body.turn_state && body.turn_state.safety_status) || (body.safety && body.safety.state);
    if (!state || state === "S0") return "";
    const net = (body.turn_state && body.turn_state.safety_net) || (body.safety && body.safety.safety_net) || {};
    const watch = (net.watch_for || []).slice(0, 4).map((item) => esc(item)).join("; ");
    const canContinue = !body.turn_state || body.turn_state.discovery_can_continue !== false;
    const label = {
      S1: "Safety information incomplete. Clarifying before any disposition.",
      S2: "Routine follow-up is reasonable. Discovery can continue.",
      S3: "Prompt in-person assessment advised.",
      S4: "Urgent in-person evaluation advised. Discovery paused.",
    }[state];
    if (!label) return "";
    return `<h2>Safety</h2><p class="ask-note" data-safety-state="${esc(state)}">${esc(state)} — ${esc(label)}</p>${watch && canContinue ? `<p class="ask-note">Watch for: ${watch}.</p>` : ""}`;
  }

  function bindComposer() {
    const form = document.getElementById("ask-form");
    const input = document.getElementById("ask-input");
    if (form) {
      form.onsubmit = async (e) => {
        e.preventDefault();
        const value = input ? input.value.trim() : "";
        await startOrContinue(value);
      };
    }
    if (input) {
      input.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          form && form.requestSubmit ? form.requestSubmit() : startOrContinue(input.value.trim());
        }
      };
    }
  }

  function emptyCase() {
    return {
      turns: [],
      memory_items: [],
      hypotheses: [],
      confidence_increasers: [],
      literature: [],
      map_version: 1,
    };
  }

  function renderThread(opts) {
    const options = opts || {};
    const body = currentCase || emptyCase();
    const pendingUser = options.pendingUser || "";
    const isThinking = !!options.thinking;
    const error = options.error || "";
    const serverTurns = body.turns || [];
    const lastServer = serverTurns[serverTurns.length - 1];
    const alreadyLogged = lastServer && lastServer.role === "user" && lastServer.text === pendingUser;
    let turnsHtml = serverTurns.map((t) =>
      `<div class="ask-msg ${t.role === "user" ? "user" : "system"}">${esc(t.text)}${t === lastServer && t.role === "system" && !isThinking ? renderFollowups(body) : ""}</div>`
    ).join("");
    if (pendingUser && !alreadyLogged) {
      turnsHtml += `<div class="ask-msg user pending" data-pending-prompt="1">${esc(pendingUser)}</div>`;
    }
    if (isThinking) {
      const label = options.thinkLabel || "Discovery Guide is thinking…";
      turnsHtml += `<div class="ask-msg system thinking" data-ask-thinking="1" aria-live="polite"><span class="ask-think-dot"></span><span class="ask-think-dot"></span><span class="ask-think-dot"></span> ${esc(label)}</div>`;
    }
    if (error) {
      turnsHtml += `<div class="ask-msg system error">${esc(error)}</div>`;
    }
    const turns = turnsHtml;
    const memory = (body.memory_items || []).slice(0, 8).map((i) => `<li>${esc(i.name)}: ${esc(i.value || "")}</li>`).join("") || "<li>No facts yet</li>";
    const gaps = (body.confidence_increasers || []).slice(0, 5).map((i) => `<li>${esc(i.label)}</li>`).join("") || "<li>No ranked gaps yet</li>";
    const hypos = (body.hypotheses || []).slice(0, 5).map((h) => `<li>${esc(h.label)}</li>`).join("") || "<li>No open families</li>";
    const cites = (body.literature || []).map((c) =>
      `<li><a href="${esc(c.url || ("https://pubmed.ncbi.nlm.nih.gov/" + c.pmid + "/"))}" target="_blank" rel="noopener">${esc(c.title || ("PMID " + c.pmid))}</a> <span class="ask-pmid">PMID ${esc(c.pmid)}</span></li>`
    ).join("") || "<li>No PubMed citations on this Case yet</li>";
    const home = (WS && currentUser && WS.workspaceHome(currentUser.role, { hash: "#dashboard" })) || "/me.html#dashboard";
    document.getElementById("ask-main").innerHTML = `
      <div class="ask-thread">
        <div>
          <div class="ask-thread-main" id="ask-thread-main">${turns}</div>
          <div class="ask-dock">
            <form class="ask-composer" id="ask-form">
              <textarea id="ask-input" rows="2" required placeholder="Ask a follow-up, or add a note…" ${sending ? "disabled" : ""}></textarea>
              <button type="submit" ${sending ? "disabled" : ""}>${sending ? "Sending…" : "Ask"}</button>
            </form>
            <p class="ask-note"><a href="${home}">Back to workspace</a> · Labs and reports are unchanged.</p>
          </div>
        </div>
        <aside class="ask-rail">
          <h2>Sources in this workspace</h2>
          <ul>
            <li><a href="${home.replace("#dashboard", "#upload")}">Uploaded labs</a></li>
            <li><a href="${home.replace("#dashboard", "#reports")}">Reports</a></li>
            <li><a href="${home.replace("#dashboard", "#evidence")}">Evidence</a></li>
          </ul>
          <h2>What we know</h2><ul>${memory}</ul>
          <h2>Investigating</h2><ul>${hypos}</ul>
          <h2>Would increase confidence</h2><ul>${gaps}</ul>
          ${renderAskSafety(body)}
          <h2>Literature</h2>
          <ul>${cites}</ul>
          <p class="ask-note">Citations come from PubMed. They are not a diagnosis.</p>
          <button type="button" class="ask-chip" data-select-value="why? show evidence">Why / show evidence</button>
          <h2>Attach a report</h2>
          <form class="ask-attach" id="ask-attach">
            <input id="ask-attach-name" type="text" placeholder="emg-report.txt" maxlength="240">
            <textarea id="ask-attach-text" rows="3" required placeholder="Paste EMG, radiology, or clinical note text. Lab files still go through workspace Upload."></textarea>
            <button type="submit">Attach report</button>
          </form>
          <p class="ask-note" id="ask-attach-status">Labs are refused here on purpose — use Upload / Analyze.</p>
          <button type="button" class="ask-chip" id="ask-add-labs">Add recommended labs</button>
          <p class="ask-note" id="ask-add-status">They appear in the existing workspace testing plan — then use Upload / Analyze as usual.</p>
          <p class="ask-note">Coverage is completeness, not disease probability. Map v${body.map_version || 1}.</p>
        </aside>
      </div>`;
    bindComposer();
    document.querySelectorAll("[data-select-value], [data-answer]").forEach((btn) => {
      btn.onclick = () => startOrContinue(btn.getAttribute("data-select-value") || btn.textContent.trim());
    });
    const attach = document.getElementById("ask-attach");
    if (attach && currentCase && currentCase.id) {
      attach.onsubmit = async (e) => {
        e.preventDefault();
        const filename = (document.getElementById("ask-attach-name").value || "").trim() || "report.txt";
        const text = (document.getElementById("ask-attach-text").value || "").trim();
        const status = document.getElementById("ask-attach-status");
        if (!text) return;
        try {
          const result = await api(`/api/v1/cases/${currentCase.id}/documents`, "POST", { filename, text });
          if (result && result.case) currentCase = result.case;
          else currentCase = await api(`/api/v1/cases/${currentCase.id}`);
          renderThread();
        } catch (err) {
          if (status) status.textContent = err.message || "Could not attach report";
        }
      };
    }
    const addLabs = document.getElementById("ask-add-labs");
    if (addLabs && currentCase && currentCase.id) {
      addLabs.onclick = async () => {
        addLabs.disabled = true;
        try {
          await api(`/api/v1/cases/${currentCase.id}/testing-plan`, "POST", { labels: [] });
          const status = document.getElementById("ask-add-status");
          if (status) status.textContent = "Added to the workspace testing plan. Use Labs / Analyze there.";
        } catch (err) {
          addLabs.disabled = false;
          const status = document.getElementById("ask-add-status");
          if (status) status.textContent = err.message || "Could not add labs";
        }
      };
    }
    const main = document.getElementById("ask-thread-main");
    if (main) main.scrollTop = main.scrollHeight;
  }

  function renderFollowups(body) {
    const interaction = body.interaction;
    if (interaction && interaction.type === "file_upload") {
      return `<div class="ask-followups"><button type="button" class="ask-chip" data-select-value="I will upload records">I will upload records</button></div>`;
    }
    if (interaction && interaction.options && interaction.options.length) {
      return `<div class="ask-followups">${interaction.options.map((opt) =>
        `<button type="button" class="ask-chip" data-select-value="${esc(opt)}">${esc(opt)}</button>`
      ).join("")}</div>`;
    }
    return "";
  }

  async function startOrContinue(text) {
    if (!text || sending) return;
    if (text.toLowerCase().includes("upload records")) {
      goWorkspace("#upload");
      return;
    }
    const clinician = WS && WS.isClinicianRole(currentUser && currentUser.role);
    if (clinician && !patientId) {
      document.getElementById("ask-main").innerHTML = `<p class="ask-home">Select a patient in the workspace first, then come back to Ask.</p>`;
      return;
    }
    sending = true;
    if (!currentCase || !currentCase.turns) currentCase = currentCase && currentCase.id ? currentCase : emptyCase();
    renderThread({ pendingUser: text, thinking: true, thinkLabel: "Discovery Guide is thinking…" });
    const input = document.getElementById("ask-input");
    if (input) input.value = "";
    try {
      const existingId = currentCase && currentCase.id;
      const path = existingId ? `/api/v1/cases/${existingId}/turns/stream` : "/api/v1/cases/stream";
      const body = existingId ? { text } : { presenting_concern: text, patient_id: patientId || null };
      await apiStream(path, body, (ev) => {
        if (ev.event === "thinking") {
          renderThread({ pendingUser: text, thinking: true, thinkLabel: ev.label || "Discovery Guide is thinking…" });
        }
        if (ev.event === "done" && ev.case) currentCase = ev.case;
        if (ev.event === "error") throw new Error(ev.detail || "Could not send that.");
      });
      if (!currentCase || !currentCase.id) {
        throw new Error("Could not open that turn.");
      }
      const next = new URL(location.href);
      next.searchParams.set("case", currentCase.id);
      if (patientId) next.searchParams.set("patient", patientId);
      history.replaceState({}, "", next);
      sending = false;
      renderThread();
    } catch (err) {
      sending = false;
      renderThread({ pendingUser: text, error: err.message || "Could not send that. Try again." });
    }
  }

  async function boot() {
    const logo = document.getElementById("ask-logo");
    if (logo && typeof herbagraphLogoLink === "function") logo.innerHTML = herbagraphLogoLink("/ask.html");
    if (!(await Auth.ensureSession())) { location.href = "/login.html?next=/ask.html"; return; }
    currentUser = await api("/api/v1/auth/me");
    const home = WS.workspaceHome(currentUser.role, { hash: "#dashboard" });
    document.getElementById("ask-workspace-link").href = home;
    document.getElementById("ask-labs-link").href = home.replace("#dashboard", "#upload");
    document.getElementById("ask-reports-link").href = home.replace("#dashboard", "#reports");
    patients = await api("/api/v1/patients");
    if (!WS.isClinicianRole(currentUser.role) && patients[0]) patientId = patients[0].id;
    if (params().get("patient")) patientId = params().get("patient");
    if (params().get("case")) {
      try {
        currentCase = await api(`/api/v1/cases/${params().get("case")}`);
        if (currentCase.patient_id) patientId = currentCase.patient_id;
        renderThread();
        return;
      } catch (_) {
        currentCase = null;
      }
    }
    renderHome();
  }

  boot().catch((err) => {
    document.getElementById("ask-main").innerHTML = `<p class="ask-home">${esc(err.message || "Could not open Ask")}</p>`;
  });
})();
