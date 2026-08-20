/* Personal Evidence — What I Learned screen (intentional empty state).
   Backend required: /api/v1/cases/{id}/attributions
   Architecture: docs/personal-evidence/PLATFORM_ARCHITECTURE.md § Attribution
   User-facing name intentionally avoids the word "Attribution" — consumer language.
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

  function renderLearned(opts) {
    opts = opts || {};
    var PE = global.HerbaGraphPersonalEvidence || {};
    var peerNav = PE.pePeerNav ? PE.pePeerNav("learned") : [];

    var subNavHtml = peerNav.length > 1 ? (
      '<nav class="pe-sub-nav" aria-label="My Evidence sections">' +
      peerNav.map(function (m) {
        var active = m.route === "learned" ? ' aria-current="page"' : "";
        return '<a class="pe-sub-nav-link' + (m.route === "learned" ? " active" : "") + '"' + active + ' href="#' + esc(m.route) + '">' + esc(m.label) + '</a>';
      }).join("") +
      '</nav>'
    ) : "";

    return (
      '<div class="pe-shell" id="pe-learned">' +
      subNavHtml +
      '<div class="pe-intentional-empty">' +
      '<div class="pe-empty-icon">' +
      '<svg viewBox="0 0 64 64" width="56" height="56" fill="none" stroke="var(--app-muted)" stroke-width="1.5">' +
      '<circle cx="32" cy="32" r="24"/>' +
      '<path d="M22 32 L28 38 L42 24"/>' +
      '<path d="M32 14 L32 22" stroke-dasharray="2 2"/>' +
      '</svg>' +
      '</div>' +
      '<h2 class="pe-empty-title">What I Learned is accumulating</h2>' +
      '<p class="pe-empty-body">This is where HerbaGraph answers the hardest question in personal health: did anything actually work? Not just "I felt better" — but the specific, evidenced, honest answer.</p>' +
      '<div class="pe-empty-features">' +
      '<div class="pe-empty-feature">' +
      '<h4>What it shows</h4>' +
      '<ul>' +
      '<li>An intervention: "Magnesium"</li>' +
      '<li>A measured change: "Sleep fragmentation decreased 14%"</li>' +
      '<li>Evidence strength: "Moderate within-person evidence"</li>' +
      '<li>What to be cautious about: "Three nights had unusually high exercise"</li>' +
      '<li>What would strengthen it: "Rechallenge after washout"</li>' +
      '</ul>' +
      '</div>' +
      '<div class="pe-empty-feature">' +
      '<h4>What it does not do</h4>' +
      '<ul>' +
      '<li>Claim that correlation is causation</li>' +
      '<li>Use population-level studies to override your personal data</li>' +
      '<li>Suppress findings that contradict its prior beliefs</li>' +
      '<li>Recommend that you stop something that is working for you</li>' +
      '</ul>' +
      '</div>' +
      '</div>' +
      '<div class="pe-empty-example">' +
      '<h4>Example of what this will look like</h4>' +
      '<div class="pe-example-card">' +
      '<div class="pe-example-pair">Magnesium → Sleep fragmentation</div>' +
      '<div class="pe-example-metric"><strong>14% decrease</strong> in sleep fragmentation</div>' +
      '<div class="pe-example-confidence">Confidence: Moderate — within-person evidence</div>' +
      '<div class="pe-example-caveat">Three nights had unusually high exercise load.</div>' +
      '<div class="pe-example-next">Would strengthen with: rechallenge after 7-day washout.</div>' +
      '</div>' +
      '</div>' +
      '<div class="pe-empty-status">' +
      '<span class="status-chip">Backend not yet wired</span>' +
      '<p class="pe-empty-note">This module activates once the Attribution analysis pipeline is implemented.</p>' +
      '</div>' +
      '</div>' +
      '</div>'
    );
  }

  function wireLearnedHandlers() {}

  global.HerbaGraphPersonalEvidence = global.HerbaGraphPersonalEvidence || {};
  global.HerbaGraphPersonalEvidence.renderLearned = renderLearned;
  global.HerbaGraphPersonalEvidence.wireLearnedHandlers = wireLearnedHandlers;

})(window);
