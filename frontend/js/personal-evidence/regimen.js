/* Personal Evidence — Regimen module.
   Renders: Today, My Current Regimen, Recent Intake.
   Consumer-facing: My Evidence > Regimen.
   No PHI in telemetry labels.
*/

(function (global) {
  "use strict";

  var PE = global.HerbaGraphPersonalEvidence || {};

  /* ── API helpers ──────────────────────────────────────────────────────── */

  function regimenApi(path, method, body, token) {
    var headers = { "Content-Type": "application/json" };
    if (token) headers.Authorization = "Bearer " + token;
    return fetch(path, { method: method, headers: headers, body: body ? JSON.stringify(body) : undefined });
  }

  /* ── Render helpers ──────────────────────────────────────────────────── */

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function relTime(iso) {
    if (!iso) return "";
    var diff = Date.now() - new Date(iso).getTime();
    var mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + "m ago";
    var hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + "h ago";
    return (Math.floor(hrs / 24)) + "d ago";
  }

  function fmtTime(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  /* ── Status chip ────────────────────────────────────────────────────── */

  function statusChipEl(item) {
    var chip = PE.statusChip(item);
    if (!chip) return "";
    return '<span class="status-chip ' + esc(chip.cls) + '">' + esc(chip.label) + "</span>";
  }

  /* ── Correction history ─────────────────────────────────────────────── */

  function correctionBadge(item) {
    var history = item && item.correction_history;
    if (!history || !history.length) return "";
    var last = history[history.length - 1];
    return (
      '<span class="prov-badge" title="Corrected at ' + esc(fmtTime(last.corrected_at)) + '">' +
      '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="M13.03 2.97a.75.75 0 0 0-1.06-1.06L6 7.94 3.03 4.97a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l6.5-6.5z" fill="currentColor"/></svg>' +
      " Corrected" +
      "</span>"
    );
  }

  /* ── Intake status indicators ───────────────────────────────────────── */

  function intakeStatusIcon(status) {
    if (status === "taken") {
      return '<svg class="intake-check" viewBox="0 0 20 20" width="16" height="16" aria-label="Taken"><circle cx="10" cy="10" r="9" fill="#2e7d57" opacity="0.15"/><path d="M6 10l3 3 5-5" stroke="#2e7d57" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }
    if (status === "skipped") {
      return '<svg class="intake-skip" viewBox="0 0 20 20" width="16" height="16" aria-label="Skipped"><circle cx="10" cy="10" r="9" fill="#69706b" opacity="0.12"/><path d="M7 13l6-6M13 13l-6-6" stroke="#69706b" stroke-width="1.5" stroke-linecap="round"/></svg>';
    }
    if (status === "partial") {
      return '<svg class="intake-partial" viewBox="0 0 20 20" width="16" height="16" aria-label="Partially taken"><circle cx="10" cy="10" r="9" fill="#b7791f" opacity="0.15"/><path d="M10 5v5l3 3" stroke="#b7791f" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>';
    }
    return "";
  }

  /* ── Single regimen item row ─────────────────────────────────────────── */

  function regimenItemRow(item, opts) {
    opts = opts || {};
    var id = esc(item && item.id || "");
    var name = esc(item && item.product_name || "Unknown product");
    var brand = item && item.product_brand ? '<span class="muted">' + esc(item.product_brand) + "</span>" : "";
    var dose = PE.itemDose(item);
    var timing = PE.itemTiming(item);
    var purpose = PE.itemPurpose(item);
    var chip = statusChipEl(item);
    var correction = correctionBadge(item);
    var taken = item && item.intake_status === "taken";
    var skipped = item && item.intake_status === "skipped";
    var partial = item && item.intake_status === "partial";
    var intakeIcon = intakeStatusIcon(item && item.intake_status);
    var isProprietary = item && item.is_proprietary_blend;
    var servingBasis = item && item.serving_basis ? item.serving_basis : "";
    var unknownFields = item && item.unknown_fields;

    var doseLine = dose
      ? '<span class="regimen-dose">' + esc(dose) + "</span>"
      : (servingBasis ? '<span class="regimen-dose muted">' + esc(servingBasis) + "</span>" : "");

    var purposeLine = purpose
      ? '<p class="regimen-purpose">Why I take this: <em>' + esc(purpose) + "</em></p>"
      : "";

    var confirmPrompt = "";
    if (unknownFields && unknownFields.length) {
      confirmPrompt =
        '<p class="regimen-confirm-prompt">' +
        "Needs confirmation: " +
        unknownFields.map(function (f) { return "Which " + esc(f) + "?"; }).join(" · ") +
        "</p>";
    }

    var intakeAction = "";
    if (!opts.noActions) {
      if (taken || partial) {
        intakeAction =
          '<span class="regimen-intake-done">' + intakeIcon + " " + (taken ? "Taken" : "Partially taken") + "</span>";
      } else if (skipped) {
        intakeAction = '<span class="regimen-intake-skipped muted">' + intakeIcon + " Skipped</span>";
      } else {
        intakeAction =
          '<div class="regimen-intake-actions">' +
          '<button type="button" class="app-btn app-btn-primary" data-action="taken" data-item-id="' + id + '">Taken</button>' +
          '<button type="button" class="app-btn" data-action="skip" data-item-id="' + id + '">Skip</button>' +
          "</div>";
      }
    }

    var blendRows = "";
    if (isProprietary && item.blend_ingredients && item.blend_ingredients.length) {
      var rows = item.blend_ingredients.map(function (ing) {
        var amt = ing.amount && ing.unit ? esc(ing.amount) + " " + esc(ing.unit) : (ing.note ? esc(ing.note) : "");
        return "<li>" + esc(ing.name) + (amt ? " — " + amt : "") + "</li>";
      }).join("");
      blendRows = '<details class="regimen-blend-details"><summary>Contains</summary><ul class="regimen-blend-list">' + rows + "</ul></details>";
    }

    return (
      '<div class="regimen-item" data-item-id="' + id + '">' +
      '<div class="regimen-item-header">' +
      '<div class="regimen-item-name">' +
      esc(name) +
      (brand ? " " + brand : "") +
      "</div>" +
      (chip ? " " + chip : "") +
      correction +
      intakeIcon +
      "</div>" +
      (doseLine ? '<div class="regimen-item-dose">' + doseLine + (timing ? ' <span class="muted">· ' + esc(timing) + "</span>" : "") + "</div>" : "") +
      purposeLine +
      confirmPrompt +
      blendRows +
      (intakeAction ? '<div class="regimen-item-actions">' + intakeAction + "</div>" : "") +
      "</div>"
    );
  }

  /* ── Period section (Today view) ─────────────────────────────────────── */

  function periodSection(period, opts) {
    opts = opts || {};
    var key = esc(period && period.key || "");
    var label = esc(period && period.period || key);
    var items = period && period.items || [];
    var allTaken = items.length > 0 && items.every(function (i) { return i.intake_status === "taken" || i.intake_status === "skipped"; });
    var someTaken = items.some(function (i) { return i.intake_status === "taken" || i.intake_status === "partial"; });

    var takenAllBtn = "";
    if (!opts.noActions && !allTaken && !someTaken && items.length > 1) {
      takenAllBtn =
        '<button type="button" class="app-btn app-btn-primary" data-action="taken-all" data-period="' + key + '">Taken all</button>';
    }

    var rows = items.map(function (item) { return regimenItemRow(item, opts); }).join("");

    return (
      '<section class="regimen-period" data-period="' + key + '">' +
      '<div class="regimen-period-header">' +
      '<h3 class="regimen-period-label">' + label + "</h3>" +
      takenAllBtn +
      "</div>" +
      '<div class="regimen-period-items">' + rows + "</div>" +
      "</section>"
    );
  }

  /* ── Today view ─────────────────────────────────────────────────────── */

  function renderTodaySection(data) {
    var periods = data && data.today && data.today.periods || [];
    if (!periods.length) {
      return (
        '<div class="empty-state">' +
        '<svg class="empty-graph" viewBox="0 0 120 80" aria-hidden="true">' +
        '<circle cx="30" cy="40" r="8" fill="none" stroke="#2e7d57" stroke-width="1"/>' +
        '<circle cx="60" cy="25" r="8" fill="none" stroke="#6978d8" stroke-width="1"/>' +
        '<circle cx="90" cy="50" r="8" fill="none" stroke="#2e7d57" stroke-width="1"/>' +
        '<line x1="38" y1="38" x2="52" y2="28" stroke="#dde1db" stroke-width="1"/>' +
        '<line x1="68" y1="28" x2="82" y2="46" stroke="#dde1db" stroke-width="1"/>' +
        "</svg>" +
        '<p class="muted">No supplements planned for today.</p>' +
        "</div>"
      );
    }

    var sections = periods.map(function (p) { return periodSection(p, { noActions: false }); }).join("");
    return (
      '<div id="regimen-today">' +
      '<h2 class="regimen-section-title">Today</h2>' +
      sections +
      "</div>"
    );
  }

  /* ── My Current Regimen ──────────────────────────────────────────────── */

  function renderMyRegimenSection(data) {
    var items = data && data.regimen && data.regimen.items || [];
    if (!items.length) {
      return (
        '<div class="empty-state">' +
        '<p class="muted">No regimen items yet.</p>' +
        '<button type="button" class="app-btn app-btn-primary" id="add-regimen-btn">Add to my regimen</button>' +
        "</div>"
      );
    }

    var rows = items
      .filter(function (i) { return i.status === "active" || i.status === "stopped"; })
      .map(function (item) { return regimenItemRow(item, { noActions: false }); })
      .join("");

    return (
      '<div id="regimen-current">' +
      '<div class="page-header-actions">' +
      '<button type="button" class="app-btn app-btn-primary" id="add-regimen-btn">+ Add to my regimen</button>' +
      "</div>" +
      '<h2 class="regimen-section-title">My Current Regimen</h2>' +
      rows +
      "</div>"
    );
  }

  /* ── Recent Intake ───────────────────────────────────────────────────── */

  function renderRecentIntakeSection(data) {
    var sessions = data && data.recent_intake || [];
    if (!sessions.length) {
      return "";
    }

    var groups = {};
    for (var i = 0; i < sessions.length; i++) {
      var s = sessions[i];
      var ts = new Date(s.taken_at);
      var isToday = ts.toDateString() === new Date().toDateString();
      var isYesterday = ts.toDateString() === new Date(Date.now() - 86400000).toDateString();
      var label = isToday ? "Today" : isYesterday ? "Yesterday" : ts.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      if (!groups[label]) groups[label] = [];
      groups[label].push(s);
    }

    var html = '<div id="regimen-recent-intake"><h2 class="regimen-section-title">Recent Intake</h2>';
    for (var label in groups) {
      html += '<p class="regimen-intake-date-label">' + esc(label) + "</p>";
      for (var j = 0; j < groups[label].length; j++) {
        var sess = groups[label][j];
        var timeStr = fmtTime(sess.taken_at);
        var itemList = (sess.items || []).map(function (it) {
          var icon = intakeStatusIcon(it.status);
          return (
            '<li class="regimen-intake-session-item">' +
            icon +
            " <strong>" + esc(it.product_name || "") + "</strong>" +
            (it.amount ? " " + esc(it.amount) + " " + esc(it.unit || "") : "") +
            (it.status === "corrected" ? ' <span class="muted">(corrected)</span>' : "") +
            "</li>"
          );
        }).join("");
        html +=
          '<div class="regimen-intake-session">' +
          '<div class="regimen-intake-session-header">' +
          '<span class="regimen-intake-session-time muted">' + esc(timeStr) + "</span>" +
          '<span class="regimen-intake-session-type">' + esc(sess.session_type || "Intake") + "</span>" +
          "</div>" +
          '<ul class="regimen-intake-session-items">' + itemList + "</ul>" +
          "</div>";
      }
    }
    html += "</div>";
    return html;
  }

  /* ── Stale version banner ──────────────────────────────────────────── */

  function staleBanner(expectedVersion) {
    return (
      '<div class="app-card" style="border-color:var(--app-warning);margin-bottom:1rem;background:rgba(183,121,31,0.06)">' +
      '<p style="color:var(--app-warning);margin:0">' +
      '<strong>This view may be stale.</strong> The regimen has been updated since this page was loaded. ' +
      "Please reload to see the current version." +
      "</p>" +
      "</div>"
    );
  }

  /* ── Feature-disabled banner ──────────────────────────────────────── */

  function disabledBanner() {
    return (
      '<div class="app-card" style="border-color:var(--app-border);margin-bottom:1rem">' +
      '<p class="muted" style="margin:0">The Regimen module is not yet available. ' +
      "This feature will be enabled in a future update.</p>" +
      "</div>"
    );
  }

  /* ── Loading skeleton ─────────────────────────────────────────────── */

  function loadingSkeleton() {
    return (
      '<div class="regimen-loading" aria-busy="true" aria-label="Loading regimen">' +
      '<div class="skeleton skeleton-line" style="width:60%;height:1.2rem;margin-bottom:0.5rem"></div>' +
      '<div class="skeleton skeleton-card" style="height:5rem;margin-bottom:0.75rem"></div>' +
      '<div class="skeleton skeleton-card" style="height:5rem;margin-bottom:0.75rem"></div>' +
      '<div class="skeleton skeleton-line" style="width:60%;height:1.2rem;margin-top:1.5rem;margin-bottom:0.5rem"></div>' +
      '<div class="skeleton skeleton-card" style="height:5rem"></div>' +
      "</div>"
    );
  }

  /* ── Error state ──────────────────────────────────────────────────── */

  function errorCard(msg) {
    return (
      '<div class="app-card app-error-card">' +
      '<p class="error">Failed to load regimen: ' + esc(msg) + "</p>" +
      '<button type="button" class="app-btn" id="regimen-retry-btn">Try again</button>' +
      "</div>"
    );
  }

  /* ── Main render ─────────────────────────────────────────────────── */

  /**
   * @param {object} opts
   * @param {string} opts.caseId
   * @param {string} opts.caseVersion
   * @param {string} opts.hgToken
   * @param {string} opts.patientId  — owner patient for regimen
   * @param {boolean} opts.enabled  — feature flag
   * @param {string} [opts.fixture]  — fixture name: 'empty'|'singleItem'|'partialIntake'|
   *                                   'needsIdentityConfirmation'|'correctedDose'|
   *                                   'proprietaryBlend'|'stale'
   * @returns {string} HTML
   */
  function renderRegimen(opts) {
    opts = opts || {};
    var fixture = opts.fixture || "singleItem";

    if (!opts.enabled) {
      PE.peIncrement && PE.peIncrement("regimen_screen_loaded_disabled");
      return disabledBanner();
    }

    PE.peIncrement && PE.peIncrement("regimen_screen_loaded");

    // Show loading skeleton while fetching
    var html = loadingSkeleton();

    // In a real implementation, fetch from the API:
    // GET /api/v1/cases/{caseId}/regimen
    // with authorization and expected_case_version.
    //
    // For now, use the typed mock fixture.
    var data = null;
    try {
      data = PE.fixture[fixture] ? PE.fixture[fixture]() : PE.fixture.singleItem();
    } catch (e) {
      data = PE.fixture.singleItem();
    }

    if (data && data.stale) {
      html = staleBanner(data.expected_version);
    } else {
      html = "";
    }

    html +=
      renderTodaySection(data) +
      renderMyRegimenSection(data) +
      renderRecentIntakeSection(data);

    return html;
  }

  /* ── Wire event handlers (called after render) ─────────────────────── */

  /**
   * Attach event handlers to rendered regimen HTML.
   * Call this after inserting the HTML into the DOM.
   */
  function wireRegimenHandlers() {
    var root = document.getElementById("app-main");
    if (!root) return;

    // Taken / Skip buttons
    root.querySelectorAll("[data-action='taken'], [data-action='skip']").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var itemId = btn.getAttribute("data-item-id");
        var action = btn.getAttribute("data-action");
        PE.peIncrement && PE.peIncrement(
          action === "taken" ? "intake_taken_clicked" : "intake_skip_clicked"
        );
        // Persist to draft so undo is possible
        var draft = PE.draft.loadDraft() || { selections: {} };
        draft.selections[itemId] = action;
        PE.draft.saveDraft(draft);
        // In real impl: POST /api/v1/cases/{caseId}/intake-sessions
        // For now: update UI optimistically
        var itemEl = root.querySelector('[data-item-id="' + itemId + '"]');
        if (itemEl) {
          var actionDiv = itemEl.querySelector(".regimen-item-actions");
          if (actionDiv) {
            actionDiv.innerHTML =
              '<span class="regimen-intake-done" style="color:var(--app-green)">' +
              intakeStatusIcon(action === "taken" ? "taken" : "skipped") +
              " " + (action === "taken" ? "Taken" : "Skipped") +
              "</span>";
          }
        }
      });
    });

    // Taken all
    root.querySelectorAll("[data-action='taken-all']").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var period = btn.getAttribute("data-period");
        PE.peIncrement && PE.peIncrement("intake_taken_all_clicked");
        var periodEl = root.querySelector('[data-period="' + period + '"]');
        if (!periodEl) return;
        var itemEls = periodEl.querySelectorAll(".regimen-item");
        var selections = {};
        itemEls.forEach(function (el) {
          var id = el.getAttribute("data-item-id");
          var actionDiv = el.querySelector(".regimen-item-actions");
          if (actionDiv) {
            actionDiv.innerHTML =
              '<span class="regimen-intake-done" style="color:var(--app-green)">' +
              intakeStatusIcon("taken") +
              " Taken</span>";
          }
          selections[id] = "taken";
        });
        // Persist to draft
        var draft = PE.draft.loadDraft() || { selections: {} };
        Object.assign(draft.selections, selections);
        PE.draft.saveDraft(draft);
      });
    });

    // Add product
    var addBtn = document.getElementById("add-regimen-btn");
    if (addBtn) {
      addBtn.addEventListener("click", function (e) {
        e.preventDefault();
        PE.peIncrement && PE.peIncrement("add_regimen_started");
        if (typeof global.renderIntakeView === "function") {
          global.renderIntakeView({ mode: "add" });
        }
      });
    }

    // Retry
    var retryBtn = document.getElementById("regimen-retry-btn");
    if (retryBtn) {
      retryBtn.addEventListener("click", function () {
        if (typeof global.refreshRegimenView === "function") {
          global.refreshRegimenView();
        }
      });
    }
  }

  /* ── Export ─────────────────────────────────────────────────────────── */

  global.HerbaGraphPersonalEvidence.renderRegimen = renderRegimen;
  global.HerbaGraphPersonalEvidence.wireRegimenHandlers = wireRegimenHandlers;

})(window);
