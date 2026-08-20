/* Personal Evidence — module registry.
   Defines all PE modules, their routes, availability, and navigation metadata.
   Architecture contract: docs/personal-evidence/PLATFORM_ARCHITECTURE.md

   Each module entry:
     {
       id:           string  — unique route key
       route:        string  — hash route (without #)
       label:        string  — user-facing nav label
       section:      string  — sidebar section: investigate | evidence | data | account
       subNav:       string  — peer group label for horizontal sub-nav
       available:    bool    — true when backend API supports this module
       description:  string  — one-line description for empty states
       apiRequired:  string  — backend API endpoint, or null
     }

   Module availability is determined by the PE_ENABLED check.
   All unavailable modules render their intentional empty state.
   No fake data, no mock-to-production shortcuts.
*/

(function (global) {
  "use strict";

  /* ── Module definitions ─────────────────────────────────────────────── */

  var MODULES = [
    {
      id: "today",
      route: "today",
      label: "Today",
      section: "evidence",
      subNav: "My Evidence",
      available: false, // backend not yet wired
      description: "Daily command center — current regimen, active signals, and experiments.",
      apiRequired: "/api/v1/cases/{id}/today",
    },
    {
      id: "regimen",
      route: "evidence",
      label: "Regimen",
      section: "evidence",
      subNav: "My Evidence",
      available: true,
      description: "What am I taking?",
      apiRequired: null, // fixture-mode works; backend: /api/v1/cases/{id}/regimen
    },
    {
      id: "signals",
      route: "signals",
      label: "Signals",
      section: "evidence",
      subNav: "My Evidence",
      available: false, // backend: /api/v1/cases/{id}/signals
      description: "What patterns are showing up?",
      apiRequired: "/api/v1/cases/{id}/signals",
    },
    {
      id: "experiments",
      route: "experiments",
      label: "Experiments",
      section: "evidence",
      subNav: "My Evidence",
      available: false, // backend: /api/v1/cases/{id}/experiments
      description: "What are we actively testing?",
      apiRequired: "/api/v1/cases/{id}/experiments",
    },
    {
      id: "learned",
      route: "learned",
      label: "What I Learned",
      section: "evidence",
      subNav: "My Evidence",
      available: false, // backend: /api/v1/cases/{id}/attributions
      description: "What have we learned from the evidence?",
      apiRequired: "/api/v1/cases/{id}/attributions",
    },
    {
      id: "passport",
      route: "passport",
      label: "Passport",
      section: "evidence",
      subNav: "My Evidence",
      available: false, // backend: /api/v1/cases/{id}/passport
      description: "My accumulated biological evidence record.",
      apiRequired: "/api/v1/cases/{id}/passport",
    },
  ];

  /* ── Lookup helpers ─────────────────────────────────────────────────── */

  function byRoute(route) {
    return MODULES.find(function (m) { return m.route === route; }) || null;
  }

  function byId(id) {
    return MODULES.find(function (m) { return m.id === id; }) || null;
  }

  function bySection(section) {
    return MODULES.filter(function (m) { return m.section === section; });
  }

  function available() {
    return MODULES.filter(function (m) { return m.available; });
  }

  function unavailable() {
    return MODULES.filter(function (m) { return !m.available; });
  }

  function peerNav(currentRoute) {
    // Return all modules sharing the same subNav group, for horizontal sub-nav.
    var current = byRoute(currentRoute);
    if (!current) return [];
    return MODULES.filter(function (m) {
      return m.subNav === current.subNav;
    });
  }

  /* ── Registry export ────────────────────────────────────────────────── */

  global.HerbaGraphPersonalEvidence = global.HerbaGraphPersonalEvidence || {};
  global.HerbaGraphPersonalEvidence.PE_MODULES = MODULES;
  global.HerbaGraphPersonalEvidence.peByRoute = byRoute;
  global.HerbaGraphPersonalEvidence.peById = byId;
  global.HerbaGraphPersonalEvidence.peBySection = bySection;
  global.HerbaGraphPersonalEvidence.peAvailable = available;
  global.HerbaGraphPersonalEvidence.peUnavailable = unavailable;
  global.HerbaGraphPersonalEvidence.pePeerNav = peerNav;

})(window);
