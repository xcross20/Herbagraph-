/* Personal Evidence — shared state, API helpers, and typed mock fixtures.
   All fixtures are synthetic. No real PHI.
   Feature flag: PERSONAL_EVIDENCE_REGIMEN_V1 must be true in the workspace
   dashboard response before any module renders.
*/

(function (global) {
  "use strict";

  /* ── Feature flag ──────────────────────────────────────────────────────── */

  /** True when the backend has activated this slice. */
  function peRegimenEnabled(dashboard) {
    const flags = dashboard && dashboard.feature_flags;
    return Boolean(flags && flags.personal_evidence_regimen_v1);
  }

  /** True when the Case Overview / My Case slice is activated. */
  function peCaseOverviewEnabled(dashboard) {
    const flags = dashboard && dashboard.feature_flags;
    return Boolean(flags && flags.case_overview_v1);
  }

  global.HerbaGraphPersonalEvidence = { peRegimenEnabled, peCaseOverviewEnabled };

  /* ── PHI-safe telemetry ───────────────────────────────────────────────── */

  /** Increment a non-PHI counter. Values must be hardcoded identifiers,
   *  never product names, ingredients, doses, or free text.
   */
  function peIncrement(metric) {
    if (typeof window !== "undefined" && window.fetch) {
      // Emit as a beacon so it never blocks the render thread.
      navigator.sendBeacon &&
        navigator.sendBeacon(
          "/api/v1/telemetry/counter?" +
            new URLSearchParams({
              m: metric,
              p: String(Date.now()),
            })
        );
    }
  }

  global.HerbaGraphPersonalEvidence.peIncrement = peIncrement;

  /* ── Intake session status labels ────────────────────────────────────── */

  function intakeStatusLabel(session) {
    const s = session && session.status;
    if (s === "submitted") return "Submitted";
    if (s === "active") return "In progress";
    if (s === "superseded") return "Superseded";
    return "Draft";
  }

  /* ── Regimen item display helpers ────────────────────────────────────── */

  function regimenItemDose(item) {
    const amt = item && (item.intended_amount || item.amount);
    const unit = item && (item.intended_unit || item.unit);
    if (!amt) return "";
    return unit ? `${amt} ${unit}` : String(amt);
  }

  function regimenItemTiming(item) {
    const timing = item && (item.schedule || item.timing_notes || item.timing);
    if (!timing) return "";
    // Humanize common schedule codes
    const MAP = {
      once_daily: "once daily",
      twice_daily: "twice daily",
      with_meals: "with meals",
      at_bedtime: "at bedtime",
      in_morning: "morning",
      in_evening: "evening",
    };
    return MAP[timing] || timing;
  }

  function regimenItemPurpose(item) {
    if (item && item.case_objective_id && item.objective_concept) {
      return item.objective_concept;
    }
    return item && item.user_purpose_note ? item.user_purpose_note : "";
  }

  function regimenItemStatusChip(item) {
    const status = item && (item.reported_vs_verified || item.status || "");
    if (status === "fully_verified") return { label: "Verified", cls: "ready" };
    if (status === "partially_verified") return { label: "Partially verified", cls: "review" };
    if (status === "reported") return { label: "Reported", cls: "no-data" };
    const idStatus = item && item.identity_resolution_status;
    if (idStatus === "unresolved") return { label: "Needs confirmation", cls: "review" };
    if (idStatus === "user_confirmed") return { label: "Confirmed", cls: "ready" };
    if (idStatus === "expert_verified") return { label: "Expert verified", cls: "ready" };
    if (status === "active") return { label: "Active", cls: "ready" };
    if (status === "stopped") return { label: "Stopped", cls: "no-data" };
    if (status === "corrected") return { label: "Corrected", cls: "review" };
    return null;
  }

  /* ── Period grouping for Today view ──────────────────────────────────── */

  function groupItemsByPeriod(items) {
    const periodOrder = ["morning", "midday", "afternoon", "evening", "bedtime", "as_needed"];
    const MAP = {
      morning: "Morning",
      midday: "Midday",
      afternoon: "Afternoon",
      evening: "Evening",
      bedtime: "Bedtime",
      as_needed: "As needed",
    };
    const groups = {};
    for (const item of items) {
      const p = (item && item.schedule) || "morning";
      const key = periodOrder.includes(p) ? p : "morning";
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    }
    const ordered = [];
    for (const p of periodOrder) {
      if (groups[p]) ordered.push({ period: MAP[p] || p, items: groups[p], key: p });
      delete groups[p];
    }
    // Remaining items that don't match known periods
    for (const [key, items] of Object.entries(groups)) {
      ordered.push({ period: key, items, key });
    }
    return ordered;
  }

  /* ── Mock fixture factory ──────────────────────────────────────────────
   * These match the typed API response shape defined in the architecture.
   * All values are synthetic.
   */

  function emptyRegimenFixture() {
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 1,
      regimen: { items: [], versions: [] },
      today: { periods: [] },
      recent_intake: [],
    };
  }

  function singleItemFixture() {
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 1,
      regimen: {
        items: [
          {
            id: "11111111-1111-1111-1111-111111111111",
            product_name: "Ashwagandha",
            product_brand: "Nootropics Depot",
            intended_amount: "300",
            intended_unit: "mg",
            schedule: "evening",
            timing_notes: "with food",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            case_objective_id: null,
            objective_concept: "sleep",
            user_purpose_note: null,
            start_date: "2026-08-01T00:00:00Z",
            stop_date: null,
            correction_history: [],
          },
        ],
        versions: [
          {
            id: "22222222-2222-2222-2222-222222222222",
            version_number: 1,
            published_at: "2026-08-01T00:00:00Z",
            status: "published",
          },
        ],
      },
      today: {
        periods: groupItemsByPeriod([
          {
            id: "11111111-1111-1111-1111-111111111111",
            product_name: "Ashwagandha",
            intended_amount: "300",
            intended_unit: "mg",
            schedule: "evening",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            intake_status: null, // not yet recorded today
          },
        ]),
      },
      recent_intake: [],
    };
  }

  function partialIntakeFixture() {
    const ts = new Date().toISOString();
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 1,
      regimen: {
        items: [
          {
            id: "aaaa1111-1111-1111-1111-111111111111",
            product_name: "Ashwagandha",
            intended_amount: "300",
            intended_unit: "mg",
            schedule: "morning",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            intake_status: "partial",
            intake_session_id: "bbbb1111-1111-1111-1111-111111111111",
          },
          {
            id: "aaaa2222-2222-2222-2222-222222222222",
            product_name: "Rhodiola",
            intended_amount: "200",
            intended_unit: "mg",
            schedule: "morning",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            intake_status: "taken",
            intake_session_id: "bbbb1111-1111-1111-1111-111111111111",
          },
          {
            id: "aaaa3333-3333-3333-3333-333333333333",
            product_name: "Vitamin D3",
            intended_amount: "2000",
            intended_unit: "IU",
            schedule: "morning",
            reported_vs_verified: "reported",
            identity_resolution_status: "unresolved",
            status: "active",
            intake_status: null,
          },
        ],
        versions: [],
      },
      today: {
        periods: groupItemsByPeriod([
          {
            id: "aaaa1111-1111-1111-1111-111111111111",
            product_name: "Ashwagandha",
            intended_amount: "300",
            intended_unit: "mg",
            schedule: "morning",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            intake_status: "partial",
          },
          {
            id: "aaaa2222-2222-2222-2222-222222222222",
            product_name: "Rhodiola",
            intended_amount: "200",
            intended_unit: "mg",
            schedule: "morning",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            intake_status: "taken",
          },
          {
            id: "aaaa3333-3333-3333-3333-333333333333",
            product_name: "Vitamin D3",
            intended_amount: "2000",
            intended_unit: "IU",
            schedule: "morning",
            reported_vs_verified: "reported",
            identity_resolution_status: "unresolved",
            status: "active",
            intake_status: null,
          },
        ]),
      },
      recent_intake: [
        {
          id: "bbbb1111-1111-1111-1111-111111111111",
          session_type: "morning",
          taken_at: ts,
          items: [
            { id: "aaaa1111-1111-1111-1111-111111111111", product_name: "Ashwagandha", amount: "300", unit: "mg", status: "partial" },
            { id: "aaaa2222-2222-2222-2222-222222222222", product_name: "Rhodiola", amount: "200", unit: "mg", status: "taken" },
          ],
        },
      ],
    };
  }

  function needsIdentityConfirmationFixture() {
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 1,
      regimen: {
        items: [
          {
            id: "cccc1111-1111-1111-1111-111111111111",
            product_name: "Magnesium",
            intended_amount: "400",
            intended_unit: "mg",
            schedule: "evening",
            reported_vs_verified: "reported",
            identity_resolution_status: "unresolved",
            status: "active",
            identity_confidence_override_reason: "Photographed before resolution",
            unknown_fields: ["form"],
          },
        ],
        versions: [],
      },
      today: {
        periods: groupItemsByPeriod([
          {
            id: "cccc1111-1111-1111-1111-111111111111",
            product_name: "Magnesium",
            intended_amount: "400",
            intended_unit: "mg",
            schedule: "evening",
            reported_vs_verified: "reported",
            identity_resolution_status: "unresolved",
            status: "active",
            unknown_fields: ["form"],
          },
        ]),
      },
      recent_intake: [],
    };
  }

  function correctedDoseFixture() {
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 2,
      regimen: {
        items: [
          {
            id: "dddd1111-1111-1111-1111-111111111111",
            product_name: "Magnesium",
            intended_amount: "250",
            intended_unit: "mg",
            schedule: "evening",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            corrected_at: "2026-08-19T21:14:00Z",
            correction_history: [
              { intended_amount: "500", corrected_at: "2026-08-18T09:00:00Z" },
              { intended_amount: "250", corrected_at: "2026-08-19T21:14:00Z" },
            ],
          },
        ],
        versions: [],
      },
      today: {
        periods: groupItemsByPeriod([
          {
            id: "dddd1111-1111-1111-1111-111111111111",
            product_name: "Magnesium",
            intended_amount: "250",
            intended_unit: "mg",
            schedule: "evening",
            reported_vs_verified: "fully_verified",
            identity_resolution_status: "user_confirmed",
            status: "active",
            correction_history: [
              { intended_amount: "500", corrected_at: "2026-08-18T09:00:00Z" },
              { intended_amount: "250", corrected_at: "2026-08-19T21:14:00Z" },
            ],
          },
        ]),
      },
      recent_intake: [
        {
          id: "eeee1111-1111-1111-1111-111111111111",
          session_type: "evening",
          taken_at: "2026-08-19T21:14:00Z",
          items: [
            { id: "dddd1111-1111-1111-1111-111111111111", product_name: "Magnesium", amount: "250", unit: "mg", status: "taken" },
          ],
        },
        {
          id: "eeee2222-2222-2222-2222-222222222222",
          session_type: "evening",
          taken_at: "2026-08-18T21:00:00Z",
          items: [
            { id: "dddd1111-1111-1111-1111-111111111111", product_name: "Magnesium", amount: "500", unit: "mg", status: "corrected" },
          ],
        },
      ],
    };
  }

  function proprietaryBlendFixture() {
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 1,
      regimen: {
        items: [
          {
            id: "ffff1111-1111-1111-1111-111111111111",
            product_name: "Athletic Greens",
            product_brand: "AG1",
            intended_amount: null,
            intended_unit: null,
            serving_basis: "1 scoop",
            schedule: "morning",
            reported_vs_verified: "reported",
            identity_resolution_status: "user_confirmed",
            status: "active",
            is_proprietary_blend: true,
            blend_ingredients: [
              { name: "Ashwagandha extract", amount: null, unit: null, note: "Amount not disclosed" },
              { name: "Rhodiola rosea", amount: null, unit: null, note: "Amount not disclosed" },
              { name: "Vitamin C", amount: "250", unit: "mg" },
              { name: "Zinc", amount: "15", unit: "mg" },
            ],
          },
        ],
        versions: [],
      },
      today: {
        periods: groupItemsByPeriod([
          {
            id: "ffff1111-1111-1111-1111-111111111111",
            product_name: "Athletic Greens",
            serving_basis: "1 scoop",
            schedule: "morning",
            is_proprietary_blend: true,
            blend_ingredients: [
              { name: "Ashwagandha extract", note: "Amount not disclosed" },
              { name: "Rhodiola rosea", note: "Amount not disclosed" },
              { name: "Vitamin C", amount: "250", unit: "mg" },
              { name: "Zinc", amount: "15", unit: "mg" },
            ],
          },
        ]),
      },
      recent_intake: [],
    };
  }

  function staleVersionFixture() {
    return {
      case_id: "00000000-0000-0000-0000-000000000001",
      case_version: 99, // stale — server will say 100
      stale: true,
      expected_version: 100,
    };
  }

  global.HerbaGraphPersonalEvidence.fixture = {
    empty: emptyRegimenFixture,
    singleItem: singleItemFixture,
    partialIntake: partialIntakeFixture,
    needsIdentityConfirmation: needsIdentityConfirmationFixture,
    correctedDose: correctedDoseFixture,
    proprietaryBlend: proprietaryBlendFixture,
    stale: staleVersionFixture,
  };

  /* ── Local draft state ─────────────────────────────────────────────────
   * Non-PHI UI state only: intake selection checkboxes, form draft fields.
   * Never treat as saved truth.
   */

  const DRAFT_KEY = "hg_pe_regimen_draft";

  function loadDraft() {
    try {
      const raw = sessionStorage.getItem(DRAFT_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function saveDraft(draft) {
    try {
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch (_) {
      /* quota exceeded — ignore */
    }
  }

  function clearDraft() {
    try {
      sessionStorage.removeItem(DRAFT_KEY);
    } catch (_) {
      /* ignore */
    }
  }

  global.HerbaGraphPersonalEvidence.draft = { loadDraft, saveDraft, clearDraft };

  /* ── Helpers ─────────────────────────────────────────────────────────── */

  global.HerbaGraphPersonalEvidence.statusLabel = intakeStatusLabel;
  global.HerbaGraphPersonalEvidence.itemDose = regimenItemDose;
  global.HerbaGraphPersonalEvidence.itemTiming = regimenItemTiming;
  global.HerbaGraphPersonalEvidence.itemPurpose = regimenItemPurpose;
  global.HerbaGraphPersonalEvidence.statusChip = regimenItemStatusChip;
  global.HerbaGraphPersonalEvidence.groupByPeriod = groupItemsByPeriod;
})(window);
