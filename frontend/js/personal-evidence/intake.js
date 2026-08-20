/* Personal Evidence — Intake Session module.
   Renders: intake session form, add product, product form fields.
   No PHI in telemetry labels.
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

  /* ── Objective presets (synthetic examples) ─────────────────────────── */

  var OBJECTIVE_PRESETS = [
    { label: "Improve sleep quality", concept: "sleep_quality", direction: "improve" },
    { label: "Reduce morning fatigue", concept: "morning_energy", direction: "increase" },
    { label: "Support stress response", concept: "stress_resilience", direction: "improve" },
    { label: "Reduce glucose variability", concept: "glucose_variability", direction: "decrease" },
    { label: "Maintain vitamin D levels", concept: "vitamin_d", direction: "stabilize" },
    { label: "Avoid daytime sedation", concept: "daytime_sedation", direction: "avoid" },
  ];

  /* ── Unit presets ─────────────────────────────────────────────────────── */

  var UNIT_PRESETS = [
    "mg", "g", "mcg", "IU", "mL", "drop", "capsule", "tablet", "tsp", "tbsp",
  ];

  /* ── Frequency presets ─────────────────────────────────────────────── */

  var FREQUENCY_PRESETS = [
    { value: "once_daily", label: "Once daily" },
    { value: "twice_daily", label: "Twice daily" },
    { value: "three_times_daily", label: "3x daily" },
    { value: "every_other_day", label: "Every other day" },
    { value: "as_needed", label: "As needed" },
    { value: "weekly", label: "Weekly" },
  ];

  /* ── Timing presets ─────────────────────────────────────────────────── */

  var TIMING_PRESETS = [
    { value: "in_morning", label: "Morning" },
    { value: "with_breakfast", label: "With breakfast" },
    { value: "midday", label: "Midday" },
    { value: "with_lunch", label: "With lunch" },
    { value: "in_evening", label: "Evening" },
    { value: "with_dinner", label: "With dinner" },
    { value: "at_bedtime", label: "At bedtime" },
    { value: "fasted", label: "Fasted" },
    { value: "with_food", label: "With food" },
  ];

  /* ── Form field helpers ─────────────────────────────────────────────── */

  function field(id, label, type, placeholder, extra) {
    extra = extra || {};
    return (
      '<div class="form-field">' +
      '<label for="' + esc(id) + '">' + esc(label) + "</label>" +
      '<input type="' + esc(type || "text") + '" ' +
      'id="' + esc(id) + '" ' +
      'name="' + esc(id) + '" ' +
      (placeholder ? 'placeholder="' + esc(placeholder) + '" ' : "") +
      (extra.required ? "required " : "") +
      (extra.autocomplete ? 'autocomplete="' + esc(extra.autocomplete) + '" ' : "") +
      'class="app-input"' +
      ">" +
      "</div>"
    );
  }

  function selectField(id, label, options, extra) {
    extra = extra || {};
    var opts = options.map(function (o) {
      var val = typeof o === "string" ? o : o.value;
      var lbl = typeof o === "string" ? o : o.label;
      return '<option value="' + esc(val) + '">' + esc(lbl) + "</option>";
    }).join("");
    return (
      '<div class="form-field">' +
      '<label for="' + esc(id) + '">' + esc(label) + "</label>" +
      '<select id="' + esc(id) + '" name="' + esc(id) + '" class="app-input">' +
      '<option value="">Select…</option>' +
      opts +
      "</select>" +
      "</div>"
    );
  }

  function textareaField(id, label, placeholder, extra) {
    extra = extra || {};
    return (
      '<div class="form-field">' +
      '<label for="' + esc(id) + '">' + esc(label) + "</label>" +
      '<textarea id="' + esc(id) + '" ' +
      'name="' + esc(id) + '" ' +
      (placeholder ? 'placeholder="' + esc(placeholder) + '" ' : "") +
      (extra.required ? "required " : "") +
      'class="app-input" rows="2"></textarea>' +
      "</div>"
    );
  }

  /* ── Single product entry form ─────────────────────────────────────── */

  function productFormFields(prefix) {
    prefix = prefix || "prod_";
    return (
      '<div class="product-form-fields">' +
      field(prefix + "name", "Product name", "text", "e.g. Ashwagandha, Magnesium glycinate", { required: true }) +
      field(prefix + "brand", "Brand (optional)", "text", "e.g. Nootropics Depot") +
      '<div class="form-row">' +
      field(prefix + "amount", "Amount", "number", "e.g. 300", { autocomplete: "off" }) +
      selectField(prefix + "unit", "Unit", UNIT_PRESETS, {}) +
      "</div>" +
      selectField(prefix + "form", "Form (optional)", [
        "Capsule", "Tablet", "Softgel", "Liquid", "Powder", "Gummy",
        "Glycinate", "Citrate", "Oxide", "Chelated", "KSM-66 extract",
        "Sensoril extract", "Standardized extract", "Other", "I don't know",
      ], {}) +
      '<div class="form-row">' +
      selectField(prefix + "frequency", "Frequency", FREQUENCY_PRESETS, {}) +
      selectField(prefix + "timing", "Timing", TIMING_PRESETS, {}) +
      "</div>" +
      textareaField(
        prefix + "purpose",
        "Why do you take this? (optional)",
        "e.g. I take this for sleep / stress / energy",
        {}
      ) +
      '<div class="form-field-intake-confidence">' +
      '<fieldset><legend>How sure are you about this dose?</legend>' +
      '<label class="confidence-label">' +
      '<input type="radio" name="' + prefix + 'confidence" value="certain"> Certain' +
      "</label>" +
      '<label class="confidence-label">' +
      '<input type="radio" name="' + prefix + 'confidence" value="estimated" checked> Estimated' +
      "</label>" +
      '<label class="confidence-label">' +
      '<input type="radio" name="' + prefix + 'confidence" value="uncertain"> Not sure' +
      "</label>" +
      "</fieldset>" +
      "</div>" +
      "</div>"
    );
  }

  /* ── Add product form ──────────────────────────────────────────────── */

  function renderAddProductForm() {
    return (
      '<div id="add-product-form" class="app-card">' +
      '<div class="page-header">' +
      '<div><h2>Add to my regimen</h2><p class="page-subtitle">Enter what you take. Exact identity can be confirmed later.</p></div>' +
      "</div>" +
      '<div id="product-form-body">' +
      '<p class="muted" style="margin-bottom:1rem;font-size:0.9rem">' +
      "All fields are optional except the product name. " +
      "Unknown fields are recorded as unknown — do not guess." +
      "</p>" +
      productFormFields("prod_") +
      '<div class="form-actions">' +
      '<button type="button" class="app-btn" id="cancel-add-product">Cancel</button>' +
      '<button type="button" class="app-btn app-btn-primary" id="submit-add-product">Add product</button>' +
      "</div>" +
      "</div>" +
      '<div id="product-form-success" hidden class="empty-state">' +
      '<svg viewBox="0 0 24 24" width="40" height="40" aria-hidden="true" style="color:var(--app-green)"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/></svg>' +
      '<p>Product added to your regimen.</p>' +
      '<button type="button" class="app-btn" id="add-another-btn">Add another</button>' +
      '<button type="button" class="app-btn app-btn-ghost" id="back-to-regimen-btn">Back to my regimen</button>' +
      "</div>" +
      "</div>"
    );
  }

  /* ── Intake objectives form ─────────────────────────────────────────── */

  function renderObjectiveForm() {
    var presets = OBJECTIVE_PRESETS.map(function (p) {
      return (
        '<label class="objective-preset-chip">' +
        '<input type="radio" name="objective_concept" value="' + esc(p.concept) + '" ' +
        'data-direction="' + esc(p.direction) + '"> ' +
        esc(p.label) +
        "</label>"
      );
    }).join("");
    return (
      '<div class="app-card" id="intake-objective-form">' +
      '<h3>What are you trying to achieve?</h3>' +
      '<p class="muted" style="margin-bottom:1rem">Select or describe your goals. This helps HerbaGraph understand why you take each product.</p>' +
      '<div class="objective-presets">' + presets + "</div>" +
      '<div style="margin-top:1rem">' +
      textareaField(
        "objective_custom",
        "Or describe in your own words (optional)",
        "e.g. I want more energy in the mornings without feeling wired at night",
        {}
      ) +
      "</div>" +
      '<div class="form-actions" style="margin-top:1rem">' +
      '<button type="button" class="app-btn" id="skip-objective-btn">Skip for now</button>' +
      '<button type="button" class="app-btn app-btn-primary" id="save-objective-btn">Continue</button>' +
      "</div>" +
      "</div>"
    );
  }

  /* ── Intake session start view ─────────────────────────────────────── */

  function renderIntakeStart() {
    return (
      '<div id="intake-start" class="app-card">' +
      '<h2>Start an intake session</h2>' +
      '<p class="muted" style="margin-bottom:1.5rem">Record what you currently take and what you are trying to achieve. ' +
      "This becomes your regimen baseline. Product identity can be confirmed separately.</p>" +
      '<div style="display:flex;flex-direction:column;gap:0.75rem;max-width:400px">' +
      '<button type="button" class="app-btn app-btn-primary" id="intake-from-objective-btn">' +
      "Start with my goals first" +
      "</button>" +
      '<button type="button" class="app-btn" id="intake-from-products-btn">' +
      "Start adding products" +
      "</button>" +
      "</div>" +
      "</div>"
    );
  }

  /* ── Product added confirmation panel ─────────────────────────────── */

  function renderProductAddedCard(product) {
    var name = esc(product && product.name || "");
    var amount = product && product.amount ? " " + esc(product.amount) + " " + esc(product.unit || "") : "";
    return (
      '<div class="app-card regimen-item" style="border-left:3px solid var(--app-green);margin-bottom:0.75rem">' +
      '<span style="color:var(--app-green);margin-right:0.5rem">Added</span>' +
      "<strong>" + name + "</strong>" + amount +
      (product.purpose ? '<p class="muted" style="margin:0.25rem 0 0">' + esc(product.purpose) + "</p>" : "") +
      "</div>"
    );
  }

  /* ── Main intake view ─────────────────────────────────────────────── */

  /**
   * @param {object} opts
   * @param {string} opts.mode  — 'start' | 'add' | 'objective'
   * @param {string} opts.caseId
   * @param {string} opts.hgToken
   * @param {string} opts.patientId
   */
  function renderIntakeView(opts) {
    opts = opts || {};
    var mode = opts.mode || "start";
    PE.peIncrement && PE.peIncrement("intake_screen_loaded_" + mode);

    if (mode === "start") {
      return renderIntakeStart() + renderObjectiveForm();
    }

    if (mode === "add") {
      return renderAddProductForm();
    }

    // Default: start
    return renderIntakeStart();
  }

  /* ── Wire intake handlers ──────────────────────────────────────────── */

  function wireIntakeHandlers() {
    var root = document.getElementById("app-main");
    if (!root) return;

    // Start with objective
    var objectiveBtn = document.getElementById("intake-from-objective-btn");
    if (objectiveBtn) {
      objectiveBtn.addEventListener("click", function () {
        PE.peIncrement && PE.peIncrement("intake_started_from_objective");
        var form = document.getElementById("intake-objective-form");
        if (form) form.scrollIntoView({ behavior: "smooth" });
      });
    }

    // Start with products
    var productsBtn = document.getElementById("intake-from-products-btn");
    if (productsBtn) {
      productsBtn.addEventListener("click", function () {
        PE.peIncrement && PE.peIncrement("intake_started_from_products");
        // Swap to product form
        var start = document.getElementById("intake-start");
        if (start) start.innerHTML = renderAddProductForm();
        wireIntakeHandlers(); // re-wire
      });
    }

    // Save objective
    var saveObjBtn = document.getElementById("save-objective-btn");
    if (saveObjBtn) {
      saveObjBtn.addEventListener("click", function () {
        PE.peIncrement && PE.peIncrement("intake_objective_confirmed");
        var custom = document.getElementById("objective_custom");
        var checked = root.querySelector('input[name="objective_concept"]:checked');
        var concept = checked ? checked.value : (custom && custom.value.trim() ? "custom:" + custom.value.trim() : "");
        var direction = checked ? checked.getAttribute("data-direction") : "";
        // In real impl: POST /api/v1/cases/{caseId}/intake-sessions
        // with purpose=intake and objective
        var draft = PE.draft.loadDraft() || {};
        draft.objective = { concept: concept, direction: direction };
        PE.draft.saveDraft(draft);
        // Swap to product form
        var form = document.getElementById("intake-objective-form");
        if (form) form.outerHTML = renderAddProductForm();
        wireIntakeHandlers();
      });
    }

    // Skip objective
    var skipObjBtn = document.getElementById("skip-objective-btn");
    if (skipObjBtn) {
      skipObjBtn.addEventListener("click", function () {
        PE.peIncrement && PE.peIncrement("intake_objective_skipped");
        var form = document.getElementById("intake-objective-form");
        if (form) form.outerHTML = renderAddProductForm();
        wireIntakeHandlers();
      });
    }

    // Cancel add product
    var cancelBtn = document.getElementById("cancel-add-product");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        PE.peIncrement && PE.peIncrement("add_regimen_cancelled");
        if (typeof global.refreshRegimenView === "function") {
          global.refreshRegimenView();
        }
      });
    }

    // Submit add product
    var submitBtn = document.getElementById("submit-add-product");
    if (submitBtn) {
      submitBtn.addEventListener("click", function () {
        PE.peIncrement && PE.peIncrement("add_regimen_submitted");
        var nameEl = document.getElementById("prod_name");
        var name = nameEl && nameEl.value.trim();
        if (!name) {
          nameEl && nameEl.focus();
          return;
        }
        var amount = (document.getElementById("prod_amount") || {}).value || "";
        var unit = (document.getElementById("prod_unit") || {}).value || "";
        var purpose = (document.getElementById("prod_purpose") || {}).value || "";
        var confidence = "estimated";
        var confEls = root.querySelectorAll('input[name="prod_confidence"]');
        for (var i = 0; i < confEls.length; i++) {
          if (confEls[i].checked) { confidence = confEls[i].value; break; }
        }
        var product = { name: name, amount: amount, unit: unit, purpose: purpose, confidence: confidence };
        // In real impl: POST /api/v1/cases/{caseId}/regimen-items
        // with status=draft; identity confirmation comes later
        var draft = PE.draft.loadDraft() || { products: [] };
        draft.products = draft.products || [];
        draft.products.push(product);
        PE.draft.saveDraft(draft);
        // Show success
        var formBody = document.getElementById("product-form-body");
        var success = document.getElementById("product-form-success");
        if (formBody) formBody.hidden = true;
        if (success) success.hidden = false;
        wireIntakeHandlers();
      });
    }

    // Add another
    var anotherBtn = document.getElementById("add-another-btn");
    if (anotherBtn) {
      anotherBtn.addEventListener("click", function () {
        var formBody = document.getElementById("product-form-body");
        var success = document.getElementById("product-form-success");
        if (formBody) {
          // Reset form
          formBody.querySelectorAll("input, textarea, select").forEach(function (el) {
            if (el.type === "radio") { el.checked = el.value === "estimated"; return; }
            el.value = "";
          });
          formBody.hidden = false;
        }
        if (success) success.hidden = true;
        document.getElementById("prod_name").focus();
      });
    }

    // Back to regimen
    var backBtn = document.getElementById("back-to-regimen-btn");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        PE.draft.clearDraft();
        if (typeof global.refreshRegimenView === "function") {
          global.refreshRegimenView();
        }
      });
    }
  }

  /* ── Export ─────────────────────────────────────────────────────────── */

  global.HerbaGraphPersonalEvidence.renderIntakeView = renderIntakeView;
  global.HerbaGraphPersonalEvidence.wireIntakeHandlers = wireIntakeHandlers;
  global.HerbaGraphPersonalEvidence.OBJECTIVE_PRESETS = OBJECTIVE_PRESETS;

})(window);
