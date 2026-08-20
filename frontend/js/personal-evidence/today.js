/* Personal Evidence — Today screen.
   Daily command center: regimen summary, active signals, active experiments.
   Renders from typed mock fixtures until the Today API is wired.
   Personal Evidence Slice 1 — MVP.
*/

(function (global) {
  "use strict";

  var PE = global.HerbaGraphPersonalEvidence || {};

  /* ── Helpers ─────────────────────────────────────────────────────────── */

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function greeting() {
    var h = new Date().getHours();
    if (h < 5)  return "Good evening";
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  }

  function todayDate() {
    return new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  }

  function statusIcon(status) {
    if (status === "taken")    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
    if (status === "skipped")   return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>';
  }

  function periodIcon(period) {
    var icons = {
      morning:   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
      evening:   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
      bedtime:   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
      afternoon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/></svg>',
      midday:    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/></svg>',
    };
    return icons[period] || icons.morning;
  }

  /* ── Today fixture ─────────────────────────────────────────────────── */

  function todayFixture() {
    var now = new Date().toISOString();
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 1,
      regimen: {
        periods: [
          {
            period: "Morning",
            key: "morning",
            items: [
              { id: "11111111-1111-1111-1111-111111111111", product_name: "Ashwagandha", intended_amount: "300", intended_unit: "mg", intake_status: "taken", taken_at: now },
              { id: "22222222-2222-2222-2222-222222222222", product_name: "Rhodiola",       intended_amount: "200", intended_unit: "mg", intake_status: "taken",  taken_at: now },
              { id: "33333333-3333-3333-3333-333333333333", product_name: "Vitamin D3",    intended_amount: "2000", intended_unit: "IU", intake_status: null },
            ],
          },
          {
            period: "Evening",
            key: "evening",
            items: [
              { id: "44444444-4444-4444-4444-444444444444", product_name: "Magnesium",      intended_amount: "400", intended_unit: "mg", intake_status: null },
              { id: "55555555-5555-5555-5555-555555555555", product_name: "Ashwagandha",    intended_amount: "300", intended_unit: "mg", intake_status: null },
            ],
          },
        ],
      },
      active_signals: [],
      active_experiments: [],
    };
  }

  /* ── Rendering ─────────────────────────────────────────────────────── */

  function periodGroup(period) {
    var items = period.items || [];
    var taken    = items.filter(function (i) { return i.intake_status === "taken"; }).length;
    var skipped  = items.filter(function (i) { return i.intake_status === "skipped"; }).length;
    var total    = items.length;
    var remaining = total - taken - skipped;

    var itemRows = items.map(function (item) {
      var icon = statusIcon(item.intake_status);
      var statusClass = item.intake_status === "taken" ? "today-item--taken"
                      : item.intake_status === "skipped" ? "today-item--skipped"
                      : "today-item--pending";
      var dose = item.intended_amount && item.intended_unit
        ? esc(item.intended_amount) + " " + esc(item.intended_unit)
        : "";
      return (
        '<div class="today-item ' + esc(statusClass) + '">' +
        '<span class="today-item-icon">' + icon + '</span>' +
        '<span class="today-item-name">' + esc(item.product_name) + '</span>' +
        (dose ? '<span class="today-item-dose muted">' + esc(dose) + '</span>' : "") +
        '<a class="today-item-action app-btn app-btn-ghost" href="#evidence?fixture=singleItem">View</a>' +
        '</div>'
      );
    }).join("");

    var summaryLabel = "";
    if (taken > 0) summaryLabel = '<span class="today-period-count today-count--taken">' + taken + ' taken</span>';
    if (skipped > 0) summaryLabel += ' <span class="today-period-count today-count--skipped">' + skipped + ' skipped</span>';
    if (remaining > 0) summaryLabel += ' <span class="today-period-count today-count--pending">' + remaining + ' pending</span>';

    return (
      '<div class="today-period">' +
      '<div class="today-period-header">' +
      '<span class="today-period-icon">' + periodIcon(period.key) + '</span>' +
      '<h3 class="today-period-name">' + esc(period.period) + '</h3>' +
      summaryLabel +
      '</div>' +
      '<div class="today-period-items">' + itemRows + '</div>' +
      '</div>'
    );
  }

  function signalsSection(signals) {
    if (!signals || !signals.length) {
      return (
        '<div class="today-section today-section--muted">' +
        '<div class="today-section-header">' +
        '<h3 class="today-section-label">Patterns</h3>' +
        '<span class="today-section-badge today-badge--future">Coming later</span>' +
        '</div>' +
        '<p class="today-empty-note">Lab correlations and symptom patterns will appear here.</p>' +
        '</div>'
      );
    }
    // Wire when signals API exists
    return "";
  }

  function experimentsSection(experiments) {
    if (!experiments || !experiments.length) {
      return (
        '<div class="today-section today-section--muted">' +
        '<div class="today-section-header">' +
        '<h3 class="today-section-label">Experiments</h3>' +
        '<span class="today-section-badge today-badge--future">Coming later</span>' +
        '</div>' +
        '<p class="today-empty-note">Active N-of-1 experiments will appear here.</p>' +
        '</div>'
      );
    }
    // Wire when experiments API exists
    return "";
  }

  /* ── Main render ───────────────────────────────────────────────────── */

  function renderToday(opts) {
    opts = opts || {};
    var data = todayFixture();

    var periods = data.regimen && data.regimen.periods || [];
    var periodSections = periods.map(periodGroup).join("");
    var hasRegimen = periods.length > 0;

    var regimenEmpty = !hasRegimen
      ? '<div class="today-empty-state">' +
          '<p class="muted">No regimen set up yet.</p>' +
          '<a class="app-btn app-btn-primary" href="#evidence">Set up my regimen</a>' +
        '</div>'
      : "";

    return (
      '<div class="pe-shell" id="pe-today">' +
      '<div class="pe-today-header">' +
      '<div>' +
      '<p class="today-greeting">' + greeting() + '</p>' +
      '<p class="today-date muted">' + todayDate() + '</p>' +
      '</div>' +
      '</div>' +

      '<div class="today-body">' +

      // Regimen summary
      '<div class="today-section">' +
      '<div class="today-section-header">' +
      '<h3 class="today-section-label">Regimen</h3>' +
      '<a class="today-section-link app-btn app-btn-ghost" href="#evidence">View full regimen</a>' +
      '</div>' +
      (regimenEmpty ||
       '<div class="today-periods">' + periodSections + '</div>') +
      '</div>' +

      // Signals
      signalsSection(data.active_signals) +

      // Experiments
      experimentsSection(data.active_experiments) +

      '</div>' + // today-body
      '</div>'   // pe-shell
    );
  }

  function wireTodayHandlers() {
    // Today is read-heavy. Actions navigate to deeper views.
  }

  /* ── Export ────────────────────────────────────────────────────────── */

  global.HerbaGraphPersonalEvidence = global.HerbaGraphPersonalEvidence || {};
  global.HerbaGraphPersonalEvidence.renderToday   = renderToday;
  global.HerbaGraphPersonalEvidence.wireTodayHandlers = wireTodayHandlers;

})(window);
