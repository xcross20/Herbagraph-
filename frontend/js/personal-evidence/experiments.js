/* Personal Evidence — Experiments screen (intentional empty state).
   Backend required: /api/v1/cases/{id}/experiments
   Architecture: docs/personal-evidence/PLATFORM_ARCHITECTURE.md § Experiments
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

  function renderExperiments(opts) {
    opts = opts || {};
    var PE = global.HerbaGraphPersonalEvidence || {};
    var peerNav = PE.pePeerNav ? PE.pePeerNav("experiments") : [];

    var subNavHtml = peerNav.length > 1 ? (
      '<nav class="pe-sub-nav" aria-label="My Evidence sections">' +
      peerNav.map(function (m) {
        var active = m.route === "experiments" ? ' aria-current="page"' : "";
        return '<a class="pe-sub-nav-link' + (m.route === "experiments" ? " active" : "") + '"' + active + ' href="#' + esc(m.route) + '">' + esc(m.label) + '</a>';
      }).join("") +
      '</nav>'
    ) : "";

    return (
      '<div class="pe-shell" id="pe-experiments">' +
      subNavHtml +
      '<div class="pe-intentional-empty">' +
      '<div class="pe-empty-icon">' +
      '<svg viewBox="0 0 64 64" width="56" height="56" fill="none" stroke="var(--app-muted)" stroke-width="1.5">' +
      '<path d="M32 8 L32 20"/>' +
      '<path d="M24 56 L32 44 L40 56"/>' +
      '<rect x="16" y="28" width="32" height="16" rx="4" stroke-dasharray="4 3"/>' +
      '<path d="M20 8 L44 8"/>' +
      '<path d="M20 8 L20 12"/>' +
      '<path d="M44 8 L44 12"/>' +
      '</svg>' +
      '</div>' +
      '<h2 class="pe-empty-title">Experiments are coming</h2>' +
      '<p class="pe-empty-body">An N-of-1 experiment is a structured way to test whether something is actually working for you. You define a question, set a baseline, run a trial, and observe the result — with HerbaGraph tracking the evidence.</p>' +
      '<div class="pe-empty-features">' +
      '<div class="pe-empty-feature">' +
      '<h4>What it looks like</h4>' +
      '<ul>' +
      '<li>A specific question: "Does evening magnesium improve my sleep fragmentation?"</li>' +
      '<li>A measurable primary outcome (e.g. sleep fragmentation, HRV)</li>' +
      '<li>A defined trial period with a control or washout phase</li>' +
      '<li>Blinded or unblinded — either way, the data speaks</li>' +
      '</ul>' +
      '</div>' +
      '<div class="pe-empty-feature">' +
      '<h4>How it differs from Signals</h4>' +
      '<ul>' +
      '<li>Signals: HerbaGraph observes what is happening</li>' +
      '<li>Experiments: you actively test a hypothesis</li>' +
      '<li>Experiments produce stronger evidence because you control the conditions</li>' +
      '<li>A well-designed experiment can rule out confounders that Signals cannot</li>' +
      '</ul>' +
      '</div>' +
      '</div>' +
      '<div class="pe-empty-status">' +
      '<span class="status-chip">Backend not yet wired</span>' +
      '<p class="pe-empty-note">This module activates once the Experiments API is implemented.</p>' +
      '</div>' +
      '</div>' +
      '</div>'
    );
  }

  function wireExperimentsHandlers() {}

  global.HerbaGraphPersonalEvidence = global.HerbaGraphPersonalEvidence || {};
  global.HerbaGraphPersonalEvidence.renderExperiments = renderExperiments;
  global.HerbaGraphPersonalEvidence.wireExperimentsHandlers = wireExperimentsHandlers;

})(window);
