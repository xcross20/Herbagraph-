/* Personal Evidence — Signals screen (intentional empty state).
   Backend required: /api/v1/cases/{id}/signals
   Architecture: docs/personal-evidence/PLATFORM_ARCHITECTURE.md § Signals
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

  function renderSignals(opts) {
    opts = opts || {};
    var PE = global.HerbaGraphPersonalEvidence || {};
    var peerNav = PE.pePeerNav ? PE.pePeerNav("signals") : [];

    var subNavHtml = peerNav.length > 1 ? (
      '<nav class="pe-sub-nav" aria-label="My Evidence sections">' +
      peerNav.map(function (m) {
        var active = m.route === "signals" ? ' aria-current="page"' : "";
        return '<a class="pe-sub-nav-link' + (m.route === "signals" ? " active" : "") + '"' + active + ' href="#' + esc(m.route) + '">' + esc(m.label) + '</a>';
      }).join("") +
      '</nav>'
    ) : "";

    return (
      '<div class="pe-shell" id="pe-signals">' +
      subNavHtml +
      '<div class="pe-intentional-empty">' +
      '<div class="pe-empty-icon">' +
      '<svg viewBox="0 0 64 64" width="56" height="56" fill="none" stroke="var(--app-muted)" stroke-width="1.5">' +
      '<polyline points="8,40 20,24 32,32 44,16 56,28"/>' +
      '<circle cx="8" cy="40" r="3" fill="var(--app-muted)"/>' +
      '<circle cx="20" cy="24" r="3" fill="var(--app-muted)"/>' +
      '<circle cx="32" cy="32" r="3" fill="var(--app-muted)"/>' +
      '<circle cx="44" cy="16" r="3" fill="var(--app-muted)"/>' +
      '<circle cx="56" cy="28" r="3" fill="var(--app-muted)"/>' +
      '<path d="M8 50 L56 50" stroke-dasharray="3 3"/>' +
      '</svg>' +
      '</div>' +
      '<h2 class="pe-empty-title">Patterns are coming</h2>' +
      '<p class="pe-empty-body">Signals emerge when lab data, symptom logs, and wearable records are tracked over time. HerbaGraph looks for consistent relationships — not just correlations, but patterns that hold across multiple observations.</p>' +
      '<div class="pe-empty-features">' +
      '<div class="pe-empty-feature">' +
      '<h4>What it looks for</h4>' +
      '<ul>' +
      '<li>Lab value changes that follow an intervention</li>' +
      '<li>Symptom frequency shifts around exposure events</li>' +
      '<li>Wearable metrics correlated with dose timing</li>' +
      '<li>Interactions between multiple interventions</li>' +
      '</ul>' +
      '</div>' +
      '<div class="pe-empty-feature">' +
      '<h4>What it does not do</h4>' +
      '<ul>' +
      '<li>Claim causation — it shows association strength</li>' +
      '<li>Recommend taking more or stopping anything</li>' +
      '<li>Show a single data point as meaningful</li>' +
      '<li>Use population averages instead of your own baseline</li>' +
      '</ul>' +
      '</div>' +
      '</div>' +
      '<div class="pe-empty-status">' +
      '<span class="status-chip">Backend not yet wired</span>' +
      '<p class="pe-empty-note">This module activates once the Signals API is implemented. No fabricated data will appear here.</p>' +
      '</div>' +
      '</div>' +
      '</div>'
    );
  }

  function wireSignalsHandlers() {
    // No interactive elements until backend exists.
  }

  global.HerbaGraphPersonalEvidence = global.HerbaGraphPersonalEvidence || {};
  global.HerbaGraphPersonalEvidence.renderSignals = renderSignals;
  global.HerbaGraphPersonalEvidence.wireSignalsHandlers = wireSignalsHandlers;

})(window);
