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

  function friendlyError(raw) {
    const text = String(raw || "");
    if (/undefinedcolumn|does not exist|sqlalchemy|asyncpg|programmingerror/i.test(text)) {
      return "Discovery storage is out of date. I could not save that turn.";
    }
    if (text.length > 240) return text.slice(0, 220) + "…";
    return text;
  }

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
      throw new Error(friendlyError(detail));
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
      throw new Error(friendlyError(raw || resp.statusText));
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
  let lastFamilies = {};
  let conversations = [];
  let hiddenConversationIds = {};

  function renderHome() {
    const clinician = WS && WS.isClinicianRole(currentUser && currentUser.role);
    document.getElementById("ask-main").innerHTML = `
      <section class="ask-home">
        <h1>Discovery Guide</h1>
        <p class="ask-lede">Tell me what's been going on. I'll connect it to what we already know about you — labs, last visit, meds — and only cite research I can actually retrieve. This is a conversation, not a diagnosis.</p>
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

  function conversationTitle(row) {
    const raw = (row && (row.presenting_concern || row.problem_representation)) || "New conversation";
    return String(raw).replace(/\s+/g, " ").trim().slice(0, 52);
  }

  function visibleConversations() {
    return conversations.filter((row) => row && row.id && !hiddenConversationIds[row.id] && row.status !== "closed");
  }

  function renderHistory() {
    const mount = document.getElementById("ask-history");
    if (!mount) return;
    const activeId = currentCase && currentCase.id;
    const rows = visibleConversations();
    mount.innerHTML = `
      <div class="ask-history-head">
        <p class="ask-history-kicker">Conversations</p>
        <button type="button" class="ask-chip" id="ask-new-chat" data-ask-new-chat="1">New chat</button>
      </div>
      <ul class="ask-history-list">
        ${rows.map((row) => `
          <li class="ask-history-item ${row.id === activeId ? "is-active" : ""}" data-conversation-id="${esc(row.id)}">
            <button type="button" class="ask-history-open" data-open-conversation="${esc(row.id)}">${esc(conversationTitle(row))}</button>
            <button type="button" class="ask-history-delete" data-delete-conversation="${esc(row.id)}" aria-label="Delete conversation">Delete</button>
          </li>`).join("") || `<li class="ask-history-empty">No saved conversations</li>`}
      </ul>`;
    const newer = document.getElementById("ask-new-chat");
    if (newer) newer.onclick = () => startNewChat();
    mount.querySelectorAll("[data-open-conversation]").forEach((btn) => {
      btn.onclick = () => openConversation(btn.getAttribute("data-open-conversation"));
    });
    mount.querySelectorAll("[data-delete-conversation]").forEach((btn) => {
      btn.onclick = (event) => {
        event.stopPropagation();
        confirmStartOver(btn.getAttribute("data-delete-conversation"));
      };
    });
  }

  async function loadConversations() {
    const qs = patientId ? `?patient_id=${patientId}` : "";
    const rows = await api("/api/v1/cases/summaries" + qs);
    conversations = Array.isArray(rows) ? rows.filter((row) => row.status !== "closed" && !hiddenConversationIds[row.id]) : [];
    renderHistory();
  }

  function rememberConversation(row) {
    if (!row || !row.id || row.status === "closed") return;
    conversations = [row, ...conversations.filter((item) => item.id !== row.id)];
    renderHistory();
  }

  async function openConversation(caseId) {
    if (!caseId) return;
    try {
      currentCase = await api(`/api/v1/cases/${caseId}`);
      if (!currentCase || currentCase.status === "closed") {
        hiddenConversationIds[caseId] = true;
        conversations = conversations.filter((item) => item.id !== caseId);
        startNewChat();
        return;
      }
      if (currentCase.patient_id) patientId = currentCase.patient_id;
      const next = new URL(location.href);
      next.searchParams.set("case", currentCase.id);
      if (patientId) next.searchParams.set("patient", patientId);
      history.replaceState({}, "", next);
      document.body.classList.remove("ask-history-open");
      renderHistory();
      renderThread();
    } catch (_) {
      hiddenConversationIds[caseId] = true;
      conversations = conversations.filter((item) => item.id !== caseId);
      renderHistory();
    }
  }

  function startNewChat() {
    currentCase = null;
    lastFamilies = {};
    const next = new URL(location.href);
    next.searchParams.delete("case");
    history.replaceState({}, "", next);
    renderHistory();
    renderHome();
    document.body.classList.remove("ask-history-open");
  }

  function renderAskControl(body) {
    const turn = body.turn_state || {};
    const control = body.control || {};
    const paused = turn.paused_concerns || [];
    const active = turn.active_concerns || [];
    const mode = turn.response_mode || ((turn.selected_action && turn.selected_action.extras && turn.selected_action.extras.response_mode) || "");
    if (!paused.length && !mode && !active.length && !control.focus) return "";
    const pausedLabel = paused.length ? paused.join(", ").split("_").join(" ") : "";
    return `<h2>Conversation control</h2>
      <p class="ask-note" data-ask-control="1">${mode ? `Response mode: ${esc(mode)}. ` : ""}${pausedLabel ? `Paused: ${esc(pausedLabel)}. Ask will not return to a paused concern unless you resume it or safety requires it.` : "No concern is paused."}</p>`;
  }

  function renderActionPlan(body) {
    const plan = body.action_plan || (body.control && body.control.action_plan);
    const snapshot = body.snapshot_id || (body.control && body.control.snapshot_id) || "";
    if (!plan && !snapshot) return "";
    const options = ((plan && plan.options) || []).map((item) =>
      `<li data-action-id="${esc(item.id || "")}">${esc(item.label)}</li>`
    ).join("");
    const avoid = ((plan && plan.avoid) || []).map((item) =>
      `<li data-action-id="${esc(item.id || "")}">${esc(item.label)}</li>`
    ).join("");
    return `<div class="ask-action-plan" data-action-plan="1" data-snapshot-id="${esc(snapshot)}">
      <h2>What can I do now?</h2>
      ${options ? `<p><strong>Low-risk options</strong></p><ul>${options}</ul>` : ""}
      ${avoid ? `<p><strong>Avoid for now</strong></p><ul>${avoid}</ul>` : ""}
      <p class="ask-note">Supportive options are not a diagnosis or treatment plan.${snapshot ? ` Snapshot ${esc(snapshot)}.` : ""}</p>
    </div>`;
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

  function bindVoice() {
    const btn = document.getElementById("ask-voice");
    const input = document.getElementById("ask-input");
    const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!btn) return;
    if (!Speech) {
      btn.hidden = true;
      return;
    }
    btn.onclick = () => {
      const rec = new Speech();
      rec.lang = "en-US";
      rec.interimResults = false;
      btn.textContent = "Listening…";
      rec.onresult = (event) => {
        const said = event.results[0] && event.results[0][0] && event.results[0][0].transcript;
        btn.textContent = "Talk";
        if (said && input) input.value = said;
        if (said) startOrContinue(said);
      };
      rec.onerror = () => { btn.textContent = "Talk"; };
      rec.onend = () => { btn.textContent = "Talk"; };
      rec.start();
    };
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
    const safetyState = (body.turn_state && body.turn_state.safety_status) || (body.safety && body.safety.state) || "";
    const paused = safetyState === "S4";
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
    const lastVisit = body.last_visit && body.last_visit.has_history
      ? `<div class="ask-last-visit"><strong>Last time</strong> ${esc(body.last_visit.summary || "")}</div>`
      : "";
    const memory = (body.memory_items || []).slice(0, 10).map((i) =>
      `<li>${esc(i.name)}: ${esc(i.value || "")} ${i.provenance === "reported" ? '<span class="ask-pmid">reported</span>' : ""} <button type="button" class="ask-mini" data-forget="${esc(i.name)}">Remove</button></li>`
    ).join("") || "<li>No facts yet</li>";
    const workup = (body.prior_workup || []).map((i) =>
      `<li>${esc(i.name)}: ${esc(i.value || "")} <span class="ask-pmid">${esc(i.verification || "patient_reported")}</span>${String(i.value || "").includes("patient_reported") || i.verification === "patient_reported" ? ' <button type="button" class="ask-mini" data-verify="${esc(i.name)}">Mark verified</button>' : ""}</li>`
    ).join("") || "<li>No prior reports yet</li>";
    const explanation = body.explanation || {};
    const families = explanation.families || [];
    const ranked = explanation.ranked_actions || [];
    const gaps = (ranked.length ? ranked : (body.confidence_increasers || [])).slice(0, 6).map((i) =>
      `<li data-candidate-id="${esc(i.id || "")}"><strong>${esc(i.label)}</strong> <span class="muted">${esc(i.why || i.reason || "This would change the picture.")}</span></li>`
    ).join("") || "<li>No ranked gaps yet</li>";
    lastFamilies = {};
    const hypos = (families.length ? families : (body.hypotheses || []).map((h) => ({id: h.code, label: h.label, rationale: (h.why_limited && h.why_limited[0]) || h.not_a_diagnosis, unknowns: h.missing_markers, evaluations: [], relationship: "", next_action: "Prepare for clinician"}))).slice(0, 6).map((h) => {
      const familyId = h.id || h.code || "";
      lastFamilies[familyId] = h;
      return `<li data-family-id="${esc(familyId)}"><strong>${esc(h.label)}</strong> <span class="ask-pmid">not a diagnosis</span>
        <button type="button" class="ask-why-open" data-why-family="${esc(familyId)}" data-explanation-drawer="1">Why is this here?</button></li>`;
    }).join("") || "<li>No open families</li>";
    const cards = (explanation.claim_cards || []).filter((c) => c.accepted && c.eligible_for_case !== false);
    const seedTitle = /grape bioactive|pink-salt composition|pink salt composition/i;
    const citeSource = cards.length ? cards : (body.literature || []).filter((c) => !seedTitle.test(c.title || "") && !String(c.source_id || "").startsWith("pmc:8567006") && !String(c.source_id || "").startsWith("pmc:7603209"));
    const cites = citeSource.map((c) =>
      `<li data-evidence-id="${esc(c.source_id || c.pmid || "")}"><a href="${esc(c.url || (c.pmid ? ("https://pubmed.ncbi.nlm.nih.gov/" + c.pmid + "/") : "#"))}"${c.url || c.pmid ? " target=\"_blank\" rel=\"noopener\"" : ""}>${esc(c.title || c.source_id || ("PMID " + c.pmid))}</a> ${c.pmid ? `<span class="ask-pmid">PMID ${esc(c.pmid)}</span>` : (c.source_id ? `<span class="ask-pmid">${esc(c.source_id)}</span>` : "")}</li>`
    ).join("") || "<li>Relevant literature is not yet available for the selected claim.</li>";
    const home = (WS && currentUser && WS.workspaceHome(currentUser.role, { hash: "#dashboard" })) || "/me.html#dashboard";
    document.getElementById("ask-main").innerHTML = `
      <div class="ask-thread">
        <div>
          <div class="ask-thread-main" id="ask-thread-main">${lastVisit}${turns}</div>
          <div class="ask-dock">
            <form class="ask-composer" id="ask-form">
              <textarea id="ask-input" rows="2" required placeholder="${paused ? "Discovery is paused for in-person evaluation." : "Ask a follow-up, or add a note…"}" ${sending || paused ? "disabled" : ""}></textarea>
              <button type="button" class="ask-voice" id="ask-voice" ${paused || sending ? "disabled" : ""}>Talk</button>
              <button type="submit" ${sending || paused ? "disabled" : ""}>${paused ? "Paused" : sending ? "Sending…" : "Ask"}</button>
            </form>
            <p class="ask-note"><a href="${home}">Back to workspace</a> · Labs and reports are unchanged. <button type="button" class="ask-mini" id="ask-start-over" data-ask-start-over="1">Start over</button></p>
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
          <h2>Prior reports</h2><ul>${workup}</ul>
          <p class="ask-note">Reported is not the same as verified. Upload the report to confirm.</p>
          <h2>Investigating</h2><ul>${hypos}</ul>
          <h2>Would increase confidence</h2><ul>${gaps}</ul>
          ${renderAskControl(body)}
          ${renderActionPlan(body)}
          ${renderAskSafety(body)}
          <h2>Literature</h2>
          <ul>${cites}</ul>
          <p class="ask-note">Citations are stored claim cards only. Missing literature is a limitation, not an invented PMID. They are not a diagnosis.</p>
          <button type="button" class="ask-chip" data-select-value="What can I do now?" data-supportive-actions="1">What can I do now?</button>
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
    bindVoice();
    document.querySelectorAll("[data-why-family]").forEach((btn) => {
      btn.onclick = () => {
        const family = lastFamilies[btn.getAttribute("data-why-family")];
        if (WS && WS.openFamilyDialog) WS.openFamilyDialog(family);
      };
    });
    const startOver = document.getElementById("ask-start-over");
    if (startOver) startOver.onclick = () => confirmStartOver(currentCase && currentCase.id);
    document.querySelectorAll("[data-why]").forEach((btn) => {
      btn.onclick = () => {
        const el = document.getElementById("why-" + btn.getAttribute("data-why"));
        if (el) el.hidden = !el.hidden;
      };
    });
    document.querySelectorAll("[data-forget]").forEach((btn) => {
      btn.onclick = async () => {
        if (!currentCase || !currentCase.id) return;
        try {
          currentCase = await api(`/api/v1/cases/${currentCase.id}/findings/${encodeURIComponent(btn.getAttribute("data-forget"))}`, "DELETE");
          renderThread();
        } catch (err) {
          btn.textContent = err.message || "Could not remove";
        }
      };
    });
    document.querySelectorAll("[data-verify]").forEach((btn) => {
      btn.onclick = async () => {
        if (!currentCase || !currentCase.id) return;
        try {
          currentCase = await api(`/api/v1/cases/${currentCase.id}/findings/${encodeURIComponent(btn.getAttribute("data-verify"))}/verify`, "POST", {});
          renderThread();
        } catch (err) {
          btn.textContent = err.message || "Could not verify";
        }
      };
    });
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

  function resetAskHome() {
    startNewChat();
  }

  function confirmStartOver(caseId) {
    if (!caseId) {
      resetAskHome();
      return;
    }
    if (document.querySelector("[data-start-over-overlay]")) return;
    const overlay = document.createElement("div");
    overlay.className = "hg-why-overlay";
    overlay.setAttribute("data-start-over-overlay", "1");
    overlay.innerHTML = `
      <div class="hg-why-dialog hg-why-dialog-confirm" role="dialog" aria-modal="true" aria-labelledby="ask-start-over-title">
        <header class="hg-why-head">
          <div>
            <p class="hg-why-kicker">Start over</p>
            <h2 id="ask-start-over-title">Delete this conversation?</h2>
          </div>
          <button type="button" class="hg-why-close" data-start-over-cancel aria-label="Cancel">Close</button>
        </header>
        <div class="hg-why-body">
          <p>This removes this chat and its investigation notes from Ask. Labs and reports stay in your workspace.</p>
          <div class="ask-continue-actions">
            <button type="button" class="ask-chip" data-start-over-cancel>Keep conversation</button>
            <button type="button" class="ask-chip ask-chip-danger" data-start-over-confirm>Delete and start over</button>
          </div>
          <p class="ask-note" data-start-over-status></p>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });
    overlay.querySelectorAll("[data-start-over-cancel]").forEach((btn) => { btn.onclick = close; });
    overlay.querySelector("[data-start-over-confirm]").onclick = async () => {
      const status = overlay.querySelector("[data-start-over-status]");
      try {
        hiddenConversationIds[caseId] = true;
        conversations = conversations.filter((item) => item.id !== caseId);
        renderHistory();
        await api(`/api/v1/cases/${caseId}`, "DELETE");
        close();
        if (currentCase && currentCase.id === caseId) startNewChat();
        else renderHistory();
      } catch (err) {
        if (status) status.textContent = err.message || "Could not delete that conversation.";
      }
    };
  }

  async function startOrContinue(text) {
    if (!text || sending) return;
    const liveState = (currentCase && currentCase.turn_state && currentCase.turn_state.safety_status) || (currentCase && currentCase.safety && currentCase.safety.state);
    if (liveState === "S4") return;
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
      rememberConversation({
        id: currentCase.id,
        presenting_concern: currentCase.presenting_concern,
        problem_representation: currentCase.problem_representation,
        status: currentCase.status,
        patient_id: currentCase.patient_id,
        updated_at: currentCase.updated_at,
      });
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
    if (WS.isClinicianRole(currentUser.role)) {
      const stored = sessionStorage.getItem("hg_active_patient_id");
      if (stored && patients.some((p) => p.id === stored)) patientId = stored;
      else if (patients[0]) patientId = patients[0].id;
    }
    if (params().get("patient")) patientId = params().get("patient");
    const toggle = document.getElementById("ask-history-toggle");
    if (toggle) {
      toggle.onclick = () => document.body.classList.toggle("ask-history-open");
    }
    try {
      await loadConversations();
    } catch (_) {
      conversations = [];
      renderHistory();
    }
    if (params().get("case")) {
      try {
        currentCase = await api(`/api/v1/cases/${params().get("case")}`);
        if (currentCase && currentCase.status === "closed") {
          resetAskHome();
          return;
        }
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
