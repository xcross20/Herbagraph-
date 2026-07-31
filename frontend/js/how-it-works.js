/** How It Works — interactive pipeline walkthrough */
(function () {
  const logo = document.getElementById("hiw-logo");
  if (logo && typeof herbagraphLogoLink === "function") {
    logo.innerHTML = herbagraphLogoLink("/");
  }

  const STAGES = [
    {
      id: 1,
      title: "Lab parser",
      short: "Parse",
      body: "Extract biomarker rows from PDF, CSV, TXT, or images. Provider-aware patterns (Quest, LabCorp, Healow) plus LLM fallback for messy OCR.",
      input: "Encrypted lab file",
      output: "ParsedLabResult[]",
    },
    {
      id: 2,
      title: "Biomarker normalizer",
      short: "Normalize",
      body: "Map 500+ portal aliases to the catalog, classify low/high/critical, and optionally run LLM alias assist for unresolved names (IMP-053).",
      input: "Raw test names + values",
      output: "NormalizedLabResult[]",
    },
    {
      id: 3,
      title: "Pathway mapper",
      short: "Pathways",
      body: "Fire pathway rules from abnormal biomarkers. Scores roll up into seven biological systems shown in the report.",
      input: "Normalized labs",
      output: "PathwayActivation[] + systems",
    },
    {
      id: 4,
      title: "Evidence retrieval",
      short: "Evidence",
      body: "Legacy path: catalog claims + live literature. Canonical path: traverse MODULATES/TARGETS graph edges, hybrid-fill with registry-filtered catalogs.",
      input: "Pathways + routing trees",
      output: "EvidenceSnippet[]",
    },
    {
      id: 5,
      title: "LLM reasoner",
      short: "Reason",
      body: "Structured recommendations anchored to retrieved evidence (stabilized to catalog when enabled). Never the sole source of truth for citations.",
      input: "Evidence + health profile",
      output: "LLMReasoningOutput",
    },
    {
      id: 6,
      title: "Safety layer",
      short: "Safety",
      body: "Drug interactions, condition contraindications, and regulated-class flags demote or exclude interventions before ranking.",
      input: "Candidate recommendations",
      output: "SafetyReport",
    },
    {
      id: 7,
      title: "Report assembly",
      short: "Report",
      body: "Confidence scoring, four-lane decision map, food sources (catalog + graph CONTAINS), explainability bundle, and disclaimers.",
      input: "Safety-cleared recs",
      output: "RecommendationReport",
    },
  ];

  const nav = document.getElementById("hiw-step-nav");
  const panel = document.getElementById("hiw-step-panel");
  const flowNodes = document.getElementById("hiw-flow-nodes");

  function renderFlow(activeId) {
    if (!flowNodes) return;
    const w = 960;
    const pad = 20;
    const nodeW = 110;
    const gap = (w - pad * 2 - nodeW * STAGES.length) / (STAGES.length - 1);
    let html = "";
    STAGES.forEach((s, i) => {
      const x = pad + i * (nodeW + gap);
      const y = 50;
      if (i < STAGES.length - 1) {
        html += `<line x1="${x + nodeW}" y1="${y + 24}" x2="${x + nodeW + gap}" y2="${y + 24}" stroke="#2e7d57" stroke-width="2" marker-end="url(#arrow)"/>`;
      }
      const cls = s.id === activeId ? "hiw-flow-node active" : "hiw-flow-node";
      html += `<g class="${cls}" transform="translate(${x},${y})">
        <rect width="${nodeW}" height="48" rx="10"/>
        <text x="${nodeW / 2}" y="20" text-anchor="middle" font-size="10" fill="#69706b">${s.id}</text>
        <text x="${nodeW / 2}" y="36" text-anchor="middle" font-weight="600">${s.short}</text>
      </g>`;
    });
    flowNodes.innerHTML = html;
  }

  function selectStage(id) {
    const stage = STAGES.find((s) => s.id === id) || STAGES[0];
    nav.querySelectorAll("button").forEach((btn) => {
      btn.setAttribute("aria-selected", btn.dataset.stage === String(stage.id) ? "true" : "false");
    });
    panel.innerHTML = `
      <h3>Stage ${stage.id}: ${stage.title}</h3>
      <p>${stage.body}</p>
      <div class="hiw-step-meta">
        <div><strong>Inputs</strong>${stage.input}</div>
        <div><strong>Outputs</strong>${stage.output}</div>
      </div>`;
    renderFlow(stage.id);
  }

  if (nav && panel) {
    nav.innerHTML = STAGES.map(
      (s) => `<li><button type="button" role="tab" data-stage="${s.id}" aria-selected="false">
        <span class="hiw-step-num">${String(s.id).padStart(2, "0")}</span>
        <span>${s.title}</span>
      </button></li>`
    ).join("");
    nav.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-stage]");
      if (!btn) return;
      selectStage(Number(btn.dataset.stage));
    });
    selectStage(1);
  }

  function barChart(el, rows, colorFrom) {
    if (!el) return;
    const max = Math.max(...rows.map((r) => r.value), 1);
    el.innerHTML = rows
      .map((r) => {
        const pct = Math.round((r.value / max) * 100);
        return `<div class="hiw-bar-row">
          <span title="${r.label}">${r.label}</span>
          <div class="hiw-bar-track"><div class="hiw-bar-fill" style="width:${pct}%;${colorFrom ? `background:${colorFrom}` : ""}"></div></div>
          <strong>${r.value}</strong>
        </div>`;
      })
      .join("");
    // animate
    requestAnimationFrame(() => {
      el.querySelectorAll(".hiw-bar-fill").forEach((fill) => {
        const w = fill.style.width;
        fill.style.width = "0%";
        requestAnimationFrame(() => {
          fill.style.width = w;
        });
      });
    });
  }

  barChart(document.getElementById("hiw-tree-chart"), [
    { label: "Nutritional", value: 50 },
    { label: "Signaling", value: 13 },
    { label: "Etiological", value: 8 },
    { label: "Culture", value: 5 },
    { label: "Autoimmune", value: 4 },
    { label: "Allergy", value: 3 },
    { label: "Celiac", value: 3 },
    { label: "PGx", value: 3 },
    { label: "Exposure", value: 2 },
  ]);

  barChart(document.getElementById("hiw-pathway-chart"), [
    { label: "HPA_AXIS", value: 41 },
    { label: "NUTRIENT_DEF", value: 38 },
    { label: "NF_KB", value: 29 },
    { label: "GI_MUCOSAL", value: 24 },
    { label: "AMPK", value: 20 },
    { label: "IRON_HEPCIDIN", value: 20 },
    { label: "ONE_CARBON", value: 16 },
    { label: "AUTOIMMUNE", value: 12 },
  ], "linear-gradient(90deg,#6978d8,#2e7d57)");
})();
