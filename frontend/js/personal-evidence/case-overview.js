/* Personal Evidence — Case Overview / My Case module.
   Renders: Investigate → My Case.
   Read-only projection of the canonical Discovery Case.

   No PHI in telemetry labels. All fixtures are synthetic.
   Feature flag: CASE_OVERVIEW_V1 must be true in workspace dashboard response.
*/

(function (global) {
  "use strict";

  var API = window.location.origin;

  /* ── API helpers ──────────────────────────────────────────────────────── */

  function coApi(path, token) {
    var headers = { "Content-Type": "application/json" };
    if (token) headers.Authorization = "Bearer " + token;
    return fetch(API + path, { method: "GET", headers: headers });
  }

  /* ── Utility ──────────────────────────────────────────────────────────── */

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtDate(iso) {
    if (!iso) return "--";
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short", day: "numeric", year: "numeric",
    });
  }

  function relTime(iso) {
    if (!iso) return "";
    var diff = Date.now() - new Date(iso).getTime();
    var mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + "m ago";
    var hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + "h ago";
    return Math.floor(hrs / 24) + "d ago";
  }

  /* ── Provenance badge ────────────────────────────────────────────────── */

  function provBadge(level) {
    var map = {
      verified: ["Verified", "prov-verified"],
      inferred: ["Inferred", "prov-inferred"],
      reported: ["Reported", "prov-reported"],
    };
    var item = map[level] || ["Reported", "prov-reported"];
    return (
      '<span class="prov-badge ' + esc(item[1]) + '">' + esc(item[0]) + "</span>"
    );
  }

  /* ── Coverage relation label ─────────────────────────────────────────── */

  function coverageLabel(relation) {
    var map = {
      DIRECTLY_ASSESSES: ["Directly assesses", "coverage-high"],
      PARTIALLY_ASSESSES: ["Partially assesses", "coverage-medium"],
      INDIRECTLY_INFORMS: ["Indirectly informs", "coverage-low"],
      DOES_NOT_DIRECTLY_ASSESS: ["Does not directly assess", "coverage-none"],
      UNKNOWN: ["Unknown coverage", "coverage-none"],
    };
    var item = map[relation] || ["Coverage unknown", "coverage-none"];
    return (
      '<span class="coverage-chip ' + esc(item[1]) + '">' + esc(item[0]) + "</span>"
    );
  }

  /* ── Finding row ─────────────────────────────────────────────────────── */

  function findingRow(f) {
    var statusChip = "";
    if (f.status === "resolved") statusChip = '<span class="status-chip ready">Resolved</span>';
    else if (f.status === "addressed") statusChip = '<span class="status-chip review">Addressed</span>';
    else if (f.status === "reported_normal" || f.status === "verified_normal")
      statusChip = '<span class="status-chip ready">Normal</span>';

    var why = "";
    if (f.why_this_is_here) {
      why =
        ' <button type="button" class="why-btn" data-why="' +
        esc(f.name) +
        '" title="Why is this here?">' +
        '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">' +
        '<circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/>' +
        '<path d="M8 5v3M8 10.5v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
        "</svg>" +
        "</button>";
    }

    return (
      '<li class="finding-item">' +
      '<span class="finding-kind">' + esc(f.kind || "finding") + "</span> " +
      '<span class="finding-name">' + esc(f.name || "") + "</span> " +
      (f.value ? '<span class="finding-value">' + esc(f.value) + "</span> " : "") +
      statusChip +
      provBadge(f.provenance) +
      why +
      "</li>"
    );
  }

  /* ── Concern section ─────────────────────────────────────────────────── */

  function concernSection(c) {
    var statusIcon = "";
    if (c.status === "resolved") statusIcon = "✓";
    else if (c.status === "addressed") statusIcon = "⟳";
    else if (c.status === "open") statusIcon = "○";

    var items = c.findings.map(function (f) { return findingRow(f); }).join("");
    return (
      '<div class="co-concern">' +
      '<div class="co-concern-header">' +
      '<span class="co-concern-icon">' + esc(statusIcon) + "</span>" +
      '<h3 class="co-concern-label">' + esc(c.label) + "</h3>" +
      '<span class="status-chip ' +
      (c.status === "resolved" ? "ready" : c.status === "addressed" ? "review" : "pending") +
      '">' + esc(c.status) + "</span>" +
      "</div>" +
      (items ? '<ul class="finding-list">' + items + "</ul>" : "") +
      "</div>"
    );
  }

  /* ── Open branch ─────────────────────────────────────────────────────── */

  function branchRow(b) {
    var tests = b.tests_conducted.map(function (t) {
      return '<span class="tag">' + esc(t) + "</span>";
    }).join("") || '<span class="muted">No tests yet</span>';
    return (
      '<li class="co-branch">' +
      '<div class="co-branch-header">' +
      '<strong>' + esc(b.branch) + "</strong>" +
      '<span class="status-chip pending">Open</span>' +
      "</div>" +
      '<p class="co-branch-label">' + esc(b.label) + "</p>" +
      '<div class="co-branch-tests">Tests: ' + tests + "</div>" +
      "</li>"
    );
  }

  /* ── Evidence gap ────────────────────────────────────────────────────── */

  function gapRow(g) {
    var sevClass = g.severity === "critical" ? "sev-critical" : g.severity === "significant" ? "sev-significant" : "sev-minor";
    return (
      '<li class="co-gap">' +
      '<span class="gap-severity ' + esc(sevClass) + '">' + esc(g.severity) + "</span>" +
      '<span class="gap-concept">' + esc(g.concept) + "</span>" +
      "</li>"
    );
  }

  /* ── Coverage explanation ─────────────────────────────────────────────── */

  function coverageExpRow(e) {
    return (
      '<li class="co-coverage-exp">' +
      '<div class="co-coverage-exp-header">' +
      '<strong>' + esc(e.branch) + "</strong>" +
      coverageLabel(e.relation) +
      "</div>" +
      '<p class="muted">' + esc(e.message) + "</p>" +
      (e.test_concepts && e.test_concepts.length
        ? '<div class="co-coverage-tests">' +
          e.test_concepts.map(function (t) { return '<span class="tag">' + esc(t) + "</span>"; }).join(" ") +
          "</div>"
        : "") +
      "</li>"
    );
  }

  /* ── Next Best Action ─────────────────────────────────────────────────── */

  function nextBestAction(nba) {
    if (!nba) return '<p class="muted">No next action available yet.</p>';
    var label = nba.label || nba.action || nba.type || "Next action";
    var reason = nba.reason || nba.why || "";
    var priority = nba.priority || nba.urgency || "";
    var priorityChip = priority
      ? '<span class="status-chip ' +
        (priority === "high" || priority === "urgent" ? "review" : "pending") +
        '">' + esc(priority) + "</span>"
      : "";
    return (
      '<div class="co-nba">' +
      '<div class="co-nba-header">' +
      '<h3>Next best action</h3>' +
      priorityChip +
      "</div>" +
      '<p class="co-nba-label"><strong>' + esc(label) + "</strong></p>" +
      (reason ? '<p class="muted co-nba-reason">' + esc(reason) + "</p>" : "") +
      "</div>"
    );
  }

  /* ── What changed ─────────────────────────────────────────────────────── */

  function whatChangedSection(changes) {
    if (!changes || !changes.length) return "";
    var items = changes.map(function (c) {
      return '<li>' + esc(c) + "</li>";
    }).join("");
    return (
      '<div class="co-section">' +
      '<h3>What changed</h3>' +
      '<ul class="co-changed-list">' + items + "</ul>" +
      "</div>"
    );
  }

  /* ── Contradictions ──────────────────────────────────────────────────── */

  function contradictionsSection(contradictions) {
    if (!contradictions || !contradictions.length) return "";
    var items = contradictions.map(function (c) {
      return '<li class="co-contradiction">' + esc(c) + "</li>";
    }).join("");
    return (
      '<div class="co-section co-contradictions">' +
      '<h3>Contradictions to resolve</h3>' +
      '<ul class="co-contradiction-list">' + items + "</ul>" +
      "</div>"
    );
  }

  /* ── Data completeness ────────────────────────────────────────────────── */

  function completenessCard(dc) {
    return (
      '<div class="co-completeness">' +
      '<div class="co-completeness-metric">' +
      '<div class="metric-value">' + esc(String(dc.investigation_coverage_percent)) + '%</div>' +
      '<div class="metric-label">Investigation coverage</div>' +
      "</div>" +
      '<div class="co-completeness-stats">' +
      '<span>' + esc(String(dc.total_findings)) + ' findings</span>' +
      '<span>' + esc(String(dc.total_hypotheses)) + ' hypotheses</span>' +
      '<span>' + esc(String(dc.open_branches)) + ' open branches</span>' +
      '<span>' + esc(String(dc.unresolved_gaps)) + ' unresolved gaps</span>' +
      "</div>" +
      "</div>"
    );
  }

  /* ── Loading state ───────────────────────────────────────────────────── */

  function loadingHTML() {
    return (
      '<div class="co-loading">' +
      '<p class="muted">Loading your case…</p>' +
      "</div>"
    );
  }

  /* ── Empty state ─────────────────────────────────────────────────────── */

  function emptyHTML() {
    return (
      '<div class="co-empty">' +
      '<svg class="empty-graph" viewBox="0 0 120 80" aria-hidden="true">' +
      '<circle cx="30" cy="40" r="8" fill="none" stroke="#2e7d57" stroke-width="1"/>' +
      '<circle cx="60" cy="25" r="8" fill="none" stroke="#6978d8" stroke-width="1"/>' +
      '<circle cx="90" cy="50" r="8" fill="none" stroke="#2e7d57" stroke-width="1"/>' +
      '<line x1="38" y1="38" x2="52" y2="28" stroke="#dde1db" stroke-width="1"/>' +
      '<line x1="68" y1="28" x2="82" y2="46" stroke="#dde1db" stroke-width="1"/>' +
      "</svg>" +
      '<h2>No case yet</h2>' +
      '<p class="muted">Start a Discovery conversation in Ask to build your case.</p>' +
      '<a class="app-btn app-btn-primary" href="/ask.html">Open Ask</a>' +
      "</div>"
    );
  }

  /* ── API error state ─────────────────────────────────────────────────── */

  function errorHTML(msg) {
    return (
      '<div class="co-error">' +
      '<h2>Could not load My Case</h2>' +
      '<p class="muted">' + esc(msg || "An unexpected error occurred.") + "</p>" +
      '<button type="button" class="app-btn" id="co-retry">Try again</button>' +
      "</div>"
    );
  }

  /* ── Full render ─────────────────────────────────────────────────────── */

  function renderCaseOverviewDOM(overview) {
    var sections = [];

    // Header
    sections.push(
      '<div class="co-header">' +
      '<h2>My Case</h2>' +
      '<div class="co-meta">' +
      '<span class="co-case-id mono">Case ' + esc(overview.case_id ? overview.case_id.slice(0, 8) : "?") + "</span>" +
      (overview.case_version
        ? '<span class="co-version">v' + esc(overview.case_version) + "</span>"
        : "") +
      (overview.snapshot_id
        ? '<span class="co-snapshot muted">Snapshot ' + esc(overview.snapshot_id) + "</span>"
        : "") +
      '<span class="co-generated muted">Updated ' + relTime(overview.generated_at) + "</span>" +
      "</div>" +
      "</div>"
    );

    // Presenting concern + status
    sections.push(
      '<div class="co-presenting-concern">' +
      '<blockquote>' + esc(overview.presenting_concern || "No concern recorded.") + "</blockquote>" +
      '<span class="status-chip ' + (overview.status === "open" ? "ready" : "pending") + '">' +
      esc(overview.status || "unknown") +
      "</span>" +
      "</div>"
    );

    // Data completeness
    if (overview.data_completeness) {
      sections.push(completenessCard(overview.data_completeness));
    }

    // Unresolved count summary
    if (overview.unresolved_count > 0) {
      sections.push(
        '<div class="co-unresolved-banner">' +
        '<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">' +
        '<path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 4a1 1 0 011 1v3a1 1 0 01-2 0V7a1 1 0 011-1zm0 8a1 1 0 100-2 1 1 0 000 2z" fill="currentColor"/>' +
        "</svg>" +
        esc(String(overview.unresolved_count)) + " unresolved item" +
        (overview.unresolved_count !== 1 ? "s" : "") +
        " — branches, gaps, and contradictions still open." +
        "</div>"
      );
    }

    // Concerns
    if (overview.concerns && overview.concerns.length) {
      sections.push(
        '<div class="co-section">' +
        "<h3>What we know</h3>" +
        overview.concerns.map(function (c) { return concernSection(c); }).join("") +
        "</div>"
      );
    }

    // Current findings (flat list)
    if (overview.current_findings && overview.current_findings.length) {
      var findingItems = overview.current_findings.map(function (f) { return findingRow(f); }).join("");
      sections.push(
        '<div class="co-section">' +
        "<h3>All current findings</h3>" +
        '<ul class="finding-list co-finding-list">' + findingItems + "</ul>" +
        "</div>"
      );
    }

    // Prior workup
    if (overview.prior_workup && overview.prior_workup.length) {
      var workupRows = overview.prior_workup.map(function (w) {
        return (
          '<li>' +
          '<span class="finding-name">' + esc(w.name || "?") + "</span> " +
          '<span class="finding-value">' + esc(w.value || "?") + "</span> " +
          '<span class="muted">(' + esc(w.verification || "reported") + ")</span>" +
          "</li>"
        );
      }).join("");
      sections.push(
        '<div class="co-section">' +
        "<h3>Prior testing</h3>" +
        '<ul class="finding-list">' + workupRows + "</ul>" +
        "</div>"
      );
    }

    // Open branches
    if (overview.open_branches && overview.open_branches.length) {
      var branchItems = overview.open_branches.map(function (b) { return branchRow(b); }).join("");
      sections.push(
        '<div class="co-section">' +
        "<h3>Open investigation branches</h3>" +
        '<ul class="co-branch-list">' + branchItems + "</ul>" +
        "</div>"
      );
    }

    // Coverage explanations
    if (overview.coverage_explanations && overview.coverage_explanations.length) {
      var covItems = overview.coverage_explanations.map(function (e) { return coverageExpRow(e); }).join("");
      sections.push(
        '<div class="co-section">' +
        "<h3>Coverage explanations</h3>" +
        '<ul class="co-coverage-list">' + covItems + "</ul>" +
        "</div>"
      );
    }

    // Evidence gaps
    if (overview.evidence_gaps && overview.evidence_gaps.length) {
      var gapItems = overview.evidence_gaps.map(function (g) { return gapRow(g); }).join("");
      sections.push(
        '<div class="co-section co-gaps">' +
        "<h3>Evidence gaps</h3>" +
        '<ul class="co-gap-list">' + gapItems + "</ul>" +
        "</div>"
      );
    }

    // Contradictions
    if (overview.contradictions && overview.contradictions.length) {
      sections.push(contradictionsSection(overview.contradictions));
    }

    // Next best action
    sections.push(
      '<div class="co-section">' +
      nextBestAction(overview.next_best_action) +
      "</div>"
    );

    // What changed
    if (overview.what_changed && overview.what_changed.length) {
      sections.push(whatChangedSection(overview.what_changed));
    }

    // Permissions note
    if (overview.permissions) {
      var perms = overview.permissions;
      var permNote =
        (perms.can_investigate ? "Investigation is open. " : "Investigation is closed. ") +
        (perms.can_export ? "Export is available." : "");
      if (permNote) {
        sections.push(
          '<p class="co-permissions-note muted">' + esc(permNote) + "</p>"
        );
      }
    }

    return sections.join("");
  }

  /* ── Public render function ───────────────────────────────────────────── */

  /**
   * Render the My Case overview.
   *
   * opts.caseId  — UUID of the case to show. Required.
   * opts.token    — auth token. Required.
   *
   * Returns a DOM-ready HTML string. Does NOT mount it.
   * Callers mount into #app-main.
   */
  function renderCaseOverview(opts) {
    if (!opts || !opts.caseId) {
      return emptyHTML();
    }
    return loadingHTML();
  }

  /**
   * Wire DOM event handlers after render. Call after mounting the HTML.
   *
   * @param {object} opts
   * @param {string} opts.caseId
   * @param {string} opts.token
   * @param {Function} opts.onRetry  — called when the retry button is clicked
   */
  function wireCaseOverviewHandlers(opts) {
    opts = opts || {};
    var retryBtn = document.getElementById("co-retry");
    if (retryBtn && opts.onRetry) {
      retryBtn.onclick = opts.onRetry;
    }

    // Wire "Why this is here" buttons
    document.querySelectorAll(".why-btn").forEach(function (btn) {
      btn.onclick = function () {
        var name = btn.getAttribute("data-why");
        var row = (opts.overview && opts.overview.current_findings || []).find(function (f) {
          return f.name === name;
        });
        var why = row && row.why_this_is_here;
        if (why) {
          alert("Why this is here: " + why);
        }
      };
    });
  }

  /**
   * Fetch the case overview from the backend and mount it.
   *
   * @param {object} opts
   * @param {string} opts.caseId
   * @param {string} opts.token
   * @param {string} opts.mountId  — DOM id to mount into. Default: "app-main"
   */
  async function mountCaseOverview(opts) {
    opts = opts || {};
    var mountId = opts.mountId || "app-main";
    var mount = document.getElementById(mountId);
    if (!mount) return;

    if (!opts.caseId) {
      mount.innerHTML = emptyHTML();
      return;
    }

    mount.innerHTML = loadingHTML();

    try {
      var resp = await coApi("/api/v1/cases/" + opts.caseId + "/overview", opts.token);
      if (resp.status === 403) {
        mount.innerHTML =
          '<div class="co-error">' +
          '<h2>My Case is not enabled</h2>' +
          '<p class="muted">Contact your administrator to request access.</p>' +
          "</div>";
        return;
      }
      if (resp.status === 404) {
        mount.innerHTML = emptyHTML();
        return;
      }
      if (!resp.ok) {
        var detail = "";
        try {
          var errBody = await resp.json();
          detail = errBody && errBody.detail ? errBody.detail : resp.statusText;
        } catch (_) {
          detail = resp.statusText;
        }
        mount.innerHTML = errorHTML(detail);
        wireCaseOverviewHandlers({
          caseId: opts.caseId,
          token: opts.token,
          overview: null,
          onRetry: function () { mountCaseOverview(opts); },
        });
        return;
      }

      var overview = await resp.json();
      mount.innerHTML = renderCaseOverviewDOM(overview);
      wireCaseOverviewHandlers({
        caseId: opts.caseId,
        token: opts.token,
        overview: overview,
        onRetry: function () { mountCaseOverview(opts); },
      });
    } catch (err) {
      mount.innerHTML = errorHTML(err && err.message ? err.message : "Network error");
      wireCaseOverviewHandlers({
        caseId: opts.caseId,
        token: opts.token,
        overview: null,
        onRetry: function () { mountCaseOverview(opts); },
      });
    }
  }

  /* ── Registry exports ────────────────────────────────────────────────── */

  global.HerbaGraphPersonalEvidence = global.HerbaGraphPersonalEvidence || {};
  global.HerbaGraphPersonalEvidence.renderCaseOverview = renderCaseOverview;
  global.HerbaGraphPersonalEvidence.mountCaseOverview = mountCaseOverview;
  global.HerbaGraphPersonalEvidence.wireCaseOverviewHandlers = wireCaseOverviewHandlers;

})(window);
