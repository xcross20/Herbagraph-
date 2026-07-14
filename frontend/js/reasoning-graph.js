/**
 * HerbaGraph interactive reasoning graph — biomarker → system → pathway → intervention → evidence → safety
 */
(function (global) {
  "use strict";

  const NODE_STYLES = {
    biomarker: { fill: "rgba(23,25,24,0.06)", stroke: "#69706b", shape: "circle" },
    system: { fill: "rgba(46,125,87,0.12)", stroke: "#2e7d57", shape: "rect" },
    pathway: { fill: "rgba(105,120,216,0.1)", stroke: "#6978d8", shape: "diamond" },
    intervention: { fill: "rgba(105,120,216,0.08)", stroke: "#6978d8", shape: "hex" },
    evidence: { fill: "transparent", stroke: "#8b95a8", shape: "circle" },
    safety: { fill: "rgba(183,121,31,0.08)", stroke: "#b7791f", shape: "shield" },
  };

  function esc(s) {
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function buildFromReport(report) {
    if (!report) return { nodes: [], edges: [], paths: [] };

    const nodes = [];
    const edges = [];
    const id = (type, label) => `${type}:${String(label).toLowerCase().replace(/\s+/g, "-")}`;

    const biomarkers = ((report.biomarker_summary || {}).measured_biomarkers || [])
      .filter(b => b.status && b.status !== "normal")
      .slice(0, 4);
    if (!biomarkers.length && report.recent_abnormal_biomarkers) {
      report.recent_abnormal_biomarkers.slice(0, 3).forEach(b => biomarkers.push(b));
    }
    biomarkers.forEach(b => {
      const name = b.biomarker_name || b.name || "Biomarker";
      nodes.push({ id: id("biomarker", name), type: "biomarker", label: name, meta: `${b.value ?? ""} ${b.unit || ""}`.trim(), detail: b.interpretation || b.status || "" });
    });

    (report.biological_systems || []).slice(0, 3).forEach(s => {
      nodes.push({ id: id("system", s.system_name), type: "system", label: s.system_name, meta: s.signal_label || "", detail: (s.drivers || []).join(", ") });
    });

    (report.pathway_activations || []).slice(0, 3).forEach(p => {
      nodes.push({ id: id("pathway", p.pathway_name), type: "pathway", label: p.pathway_name, meta: p.direction || "", detail: (p.contributing_biomarkers || []).join(", ") });
    });

    (report.recommendations || []).slice(0, 4).forEach(r => {
      nodes.push({
        id: id("intervention", r.intervention_name),
        type: "intervention",
        label: r.intervention_name,
        meta: r.evidence_tier_label || r.evidence_level || "",
        detail: r.rationale || r.mechanism || "",
        recommendation: r,
      });
    });

    nodes.push({ id: "evidence:layer", type: "evidence", label: "Evidence", meta: `${(report.citations || []).length} sources`, detail: "Inspectable citations and confidence bands" });
    nodes.push({ id: "safety:layer", type: "safety", label: "Safety", meta: (report.safety_summary || {}).overall_note ? "Review" : "Clear", detail: (report.safety_summary || {}).overall_note || "No contraindications flagged" });

    const bioIds = nodes.filter(n => n.type === "biomarker").map(n => n.id);
    const sysIds = nodes.filter(n => n.type === "system").map(n => n.id);
    const pathIds = nodes.filter(n => n.type === "pathway").map(n => n.id);
    const intvIds = nodes.filter(n => n.type === "intervention").map(n => n.id);

    bioIds.forEach((b, i) => { if (sysIds[i]) edges.push({ from: b, to: sysIds[i], active: i === 0 }); else if (sysIds[0]) edges.push({ from: b, to: sysIds[0], active: i === 0 }); });
    sysIds.forEach((s, i) => { if (pathIds[i]) edges.push({ from: s, to: pathIds[i], active: i === 0 }); });
    pathIds.forEach((p, i) => { if (intvIds[i]) edges.push({ from: p, to: intvIds[i], active: i === 0 }); else if (intvIds[0]) edges.push({ from: p, to: intvIds[0], active: false }); });
    intvIds.forEach(i => {
      edges.push({ from: i, to: "evidence:layer", active: false });
      edges.push({ from: i, to: "safety:layer", active: false });
    });

    const paths = (report.recommendations || []).slice(0, 3).map(r => buildReasoningPathSteps(report, r));

    return { nodes, edges, paths };
  }

  function buildReasoningPathSteps(report, rec) {
    const biomarker = ((report.biomarker_summary || {}).measured_biomarkers || []).find(b => b.status !== "normal")
      || { biomarker_name: "Biomarker signal" };
    const system = (report.biological_systems || [])[0];
    const pathway = (report.pathway_activations || [])[0];
    return [
      { type: "biomarker", label: biomarker.biomarker_name || "Biomarker", meta: biomarker.status || "" },
      { type: "system", label: system?.system_name || "Biological system", meta: system?.signal_label || "" },
      { type: "pathway", label: pathway?.pathway_name || rec.mechanism?.split(" ").slice(0, 3).join(" ") || "Pathway relevance", meta: "" },
      { type: "intervention", label: rec.intervention_name, meta: rec.evidence_tier_label || "" },
      { type: "evidence", label: `Human evidence: ${rec.evidence_level || rec.evidence_tier_label || "moderate"}`, meta: `${(rec.cited_study_ids || []).length} sources` },
      { type: "safety", label: rec.safety_risk && rec.safety_risk !== "low" ? "Safety review required" : "Safety: acceptable", meta: rec.safety_risk || "low" },
    ];
  }

  function renderPathHtml(steps, options) {
    options = options || {};
    const interactive = options.interactive !== false;
    return `<div class="reasoning-path${interactive ? " reasoning-path-interactive" : ""}" role="list">${steps.map((step, i) => `
      <div class="reasoning-path-step" role="listitem" data-step-type="${esc(step.type)}" ${interactive ? `data-step-index="${i}"` : ""}>
        <span class="reasoning-path-node reasoning-path-node-${esc(step.type)}">${esc(step.label)}</span>
        ${step.meta ? `<span class="reasoning-path-meta">${esc(step.meta)}</span>` : ""}
      </div>
      ${i < steps.length - 1 ? '<span class="reasoning-path-arrow" aria-hidden="true">↓</span>' : ""}
    `).join("")}</div>`;
  }

  function abbrevLabel(label, max) {
    const text = String(label || "").trim();
    if (text.length <= max) return text;
    const words = text.split(/\s+/);
    if (words.length > 1 && words[0].length + 3 <= max) return words[0] + "…";
    return text.slice(0, Math.max(4, max - 1)) + "…";
  }

  function labelWidth(label, type) {
    const len = String(label || "").length;
    if (type === "system") return Math.min(120, Math.max(76, len * 5.5));
    if (type === "pathway") return Math.min(110, Math.max(72, len * 5.2));
    if (type === "intervention") return Math.min(100, Math.max(68, len * 5));
    return 68;
  }

  function layoutNodes(nodes, width, height) {
    const cols = { biomarker: 0.1, system: 0.34, pathway: 0.56, intervention: 0.78, evidence: 0.9, safety: 0.9 };
    const rowForType = { biomarker: 0.22, system: 0.38, pathway: 0.54, intervention: 0.72, evidence: 0.86, safety: 0.94 };
    const placed = {};
    const typeCounts = {};
    nodes.forEach(n => {
      typeCounts[n.type] = (typeCounts[n.type] || 0) + 1;
    });
    const typeIndex = {};
    return nodes.map(n => {
      const idx = typeIndex[n.type] || 0;
      typeIndex[n.type] = idx + 1;
      const count = typeCounts[n.type] || 1;
      const x = (cols[n.type] ?? 0.5) * width;
      const baseY = (rowForType[n.type] ?? 0.5) * height;
      const y = baseY + (idx - (count - 1) / 2) * 36;
      placed[n.id] = { x, y };
      return { ...n, x, y };
    });
  }

  function mount(container, graphData, options) {
    options = options || {};
    if (!container || !graphData) return null;

    const width = options.width || 560;
    const height = options.height || 360;
    const nodes = layoutNodes(graphData.nodes, width, height);
    const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
    let selectedId = nodes.find(n => n.type === "biomarker")?.id || nodes[0]?.id;

    const detailEl = container.querySelector("[data-graph-detail]") || container.parentElement?.querySelector("[data-graph-detail]");

    function highlightPath(nodeId) {
      selectedId = nodeId;
      const node = nodeMap[nodeId];
      if (!node) return;
      container.querySelectorAll(".rg-node").forEach(el => {
        const active = el.dataset.nodeId === nodeId;
        const related = graphData.edges.some(e =>
          (e.from === nodeId && el.dataset.nodeId === e.to) || (e.to === nodeId && el.dataset.nodeId === e.from)
        );
        el.classList.toggle("is-active", active);
        el.classList.toggle("is-related", !active && related);
      });
      container.querySelectorAll(".rg-edge").forEach(el => {
        const on = el.dataset.from === nodeId || el.dataset.to === nodeId;
        el.classList.toggle("is-active", on);
      });
      if (detailEl) {
        detailEl.innerHTML = `<strong>${esc(node.label)}</strong>
          <p class="muted" style="margin:0.35rem 0 0">${esc(node.type)} · ${esc(node.meta || "")}</p>
          ${node.detail ? `<p style="margin:0.5rem 0 0;font-size:0.88rem">${esc(node.detail)}</p>` : ""}`;
      }
      if (options.onSelect) options.onSelect(node);
    }

    const edgesSvg = graphData.edges.map(e => {
      const a = nodeMap[e.from];
      const b = nodeMap[e.to];
      if (!a || !b) return "";
      return `<line class="rg-edge${e.active ? " is-active" : ""}" data-from="${esc(e.from)}" data-to="${esc(e.to)}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" />`;
    }).join("");

    const nodesSvg = nodes.map(n => {
      const st = NODE_STYLES[n.type] || NODE_STYLES.biomarker;
      const active = n.id === selectedId;
      let shape = "";
      if (st.shape === "circle") {
        shape = `<circle class="rg-node${active ? " is-active" : ""}" data-node-id="${esc(n.id)}" data-node-type="${esc(n.type)}" cx="${n.x}" cy="${n.y}" r="22" tabindex="0" role="button" aria-label="${esc(n.label)}"/>`;
      } else if (st.shape === "rect") {
        const w = labelWidth(n.label, n.type);
        shape = `<rect class="rg-node${active ? " is-active" : ""}" data-node-id="${esc(n.id)}" data-node-type="${esc(n.type)}" x="${n.x - w / 2}" y="${n.y - 15}" width="${w}" height="30" rx="10" tabindex="0" role="button" aria-label="${esc(n.label)}"/>`;
      } else if (st.shape === "diamond") {
        shape = `<polygon class="rg-node${active ? " is-active" : ""}" data-node-id="${esc(n.id)}" data-node-type="${esc(n.type)}" points="${n.x},${n.y - 18} ${n.x + 22},${n.y} ${n.x},${n.y + 18} ${n.x - 22},${n.y}" tabindex="0" role="button" aria-label="${esc(n.label)}"/>`;
      } else if (st.shape === "hex") {
        shape = `<polygon class="rg-node${active ? " is-active" : ""}" data-node-id="${esc(n.id)}" data-node-type="${esc(n.type)}" points="${n.x - 20},${n.y} ${n.x - 10},${n.y - 16} ${n.x + 10},${n.y - 16} ${n.x + 20},${n.y} ${n.x + 10},${n.y + 16} ${n.x - 10},${n.y + 16}" tabindex="0" role="button" aria-label="${esc(n.label)}"/>`;
      } else {
        shape = `<circle class="rg-node${active ? " is-active" : ""}" data-node-id="${esc(n.id)}" data-node-type="${esc(n.type)}" cx="${n.x}" cy="${n.y}" r="18" tabindex="0" role="button" aria-label="${esc(n.label)}"/>`;
      }
      const short = abbrevLabel(n.label, n.type === "system" ? 18 : 16);
      return `${shape}<title>${esc(n.label)}</title><text class="rg-label" x="${n.x}" y="${n.y + 36}" text-anchor="middle">${esc(short)}</text>`;
    }).join("");

    container.innerHTML = `<svg class="reasoning-graph-svg" viewBox="0 0 ${width} ${height}" aria-label="Biological reasoning graph">
      <defs>
        <filter id="rg-glow"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <g class="rg-edges">${edgesSvg}</g>
      <g class="rg-nodes">${nodesSvg}</g>
    </svg>`;

    container.querySelectorAll(".rg-node").forEach(el => {
      const handler = () => highlightPath(el.dataset.nodeId);
      el.addEventListener("click", handler);
      el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handler(); } });
    });

    if (selectedId) highlightPath(selectedId);
    return { highlight: highlightPath, data: graphData };
  }

  global.HerbaGraphReasoningGraph = {
    NODE_STYLES,
    buildFromReport,
    buildReasoningPathSteps,
    renderPathHtml,
    mount,
  };
})(window);