/* Personal Evidence — Passport screen (intentional empty state).
   Backend required: /api/v1/cases/{id}/passport
   Architecture: docs/personal-evidence/PLATFORM_ARCHITECTURE.md § Passport
*/

(function (global) {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function statRow(label, value, note) {
    return (
      '<div class="passport-stat">' +
      '<div class="passport-stat-value">' + esc(value || "—") + '</div>' +
      '<div class="passport-stat-label">' + esc(label) + '</div>' +
      (note ? '<div class="passport-stat-note muted">' + esc(note) + '</div>' : "") +
      '</div>'
    );
  }

  function renderPassport(opts) {
    opts = opts || {};
    var PE = global.HerbaGraphPersonalEvidence || {};
    var peerNav = PE.pePeerNav ? PE.pePeerNav("passport") : [];

    var subNavHtml = peerNav.length > 1 ? (
      '<nav class="pe-sub-nav" aria-label="My Evidence sections">' +
      peerNav.map(function (m) {
        var active = m.route === "passport" ? ' aria-current="page"' : "";
        return '<a class="pe-sub-nav-link' + (m.route === "passport" ? " active" : "") + '"' + active + ' href="#' + esc(m.route) + '">' + esc(m.label) + '</a>';
      }).join("") +
      '</nav>'
    ) : "";

    return (
      '<div class="pe-shell" id="pe-passport">' +
      subNavHtml +
      '<div class="pe-intentional-empty">' +
      '<div class="pe-empty-icon">' +
      '<svg viewBox="0 0 64 64" width="56" height="56" fill="none" stroke="var(--app-muted)" stroke-width="1.5">' +
      '<rect x="8" y="16" width="48" height="36" rx="4"/>' +
      '<circle cx="20" cy="34" r="6"/>' +
      '<path d="M30 30 L44 30 M30 36 L44 36 M30 42 L40 42"/>' +
      '<path d="M16 12 L16 16"/>' +
      '<path d="M48 12 L48 16"/>' +
      '</svg>' +
      '</div>' +
      '<h2 class="pe-empty-title">Your Evidence Passport is forming</h2>' +
      '<p class="pe-empty-body">The Passport is the durable record of your personal biological evidence journey. It synthesizes investigations, interventions, outcomes, and learning into a clinician-ready format you own and control.</p>' +
      '<div class="pe-empty-features">' +
      '<div class="pe-empty-feature">' +
      '<h4>What it will contain</h4>' +
      '<ul>' +
      '<li>Investigations conducted and their conclusions</li>' +
      '<li>Interventions tested with outcomes</li>' +
      '<li>Personal evidence findings from experiments and signals</li>' +
      '<li>Current regimen snapshot</li>' +
      '<li>Unresolved questions for further investigation</li>' +
      '</ul>' +
      '</div>' +
      '<div class="pe-empty-feature">' +
      '<h4>How it differs from a report</h4>' +
      '<ul>' +
      '<li>A report is an output from one lab upload</li>' +
      '<li>The Passport is the accumulated record across all time</li>' +
      '<li>The Passport is personal evidence, not literature synthesis</li>' +
      '<li>It is shareable with clinicians in a clean, provable format</li>' +
      '</ul>' +
      '</div>' +
      '</div>' +
      '<h4 class="pe-empty-subheading">Example of what this will look like</h4>' +
      '<div class="passport-preview">' +
      '<div class="passport-preview-header">My Evidence Passport</div>' +
      '<div class="passport-stats-grid">' +
      statRow("Investigations", "—", "Coming as you use Ask") +
      statRow("Interventions tested", "—", "Building from Regimen") +
      statRow("Personal findings", "—", "From What I Learned") +
      statRow("Current regimen items", "—", "Synced from Regimen") +
      statRow("Unresolved questions", "—", "Carried from Ask") +
      '</div>' +
      '<div class="passport-preview-actions">' +
      '<button class="app-btn" disabled>Export PDF</button>' +
      '<button class="app-btn" disabled>Share with clinician</button>' +
      '</div>' +
      '</div>' +
      '<div class="pe-empty-status">' +
      '<span class="status-chip">Backend not yet wired</span>' +
      '<p class="pe-empty-note">This module activates once the Passport synthesis API is implemented. It aggregates data from Regimen, Signals, Experiments, and What I Learned.</p>' +
      '</div>' +
      '</div>' +
      '</div>'
    );
  }

  function wirePassportHandlers() {}

  global.HerbaGraphPersonalEvidence = global.HerbaGraphPersonalEvidence || {};
  global.HerbaGraphPersonalEvidence.renderPassport = renderPassport;
  global.HerbaGraphPersonalEvidence.wirePassportHandlers = wirePassportHandlers;

})(window);
