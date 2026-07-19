/**
 * Knowledge path chooser — A/B between legacy catalogs and canonical graph.
 * Usage: const path = await window.hgPickKnowledgePath(); // 'legacy' | 'canonical' | null
 */
(function (global) {
  const STORAGE_KEY = "hg_preferred_knowledge_path";

  function preferredPath() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v === "legacy" || v === "canonical") return v;
    } catch (_) { /* ignore */ }
    return "legacy";
  }

  function rememberPath(path) {
    try {
      localStorage.setItem(STORAGE_KEY, path);
    } catch (_) { /* ignore */ }
  }

  function ensureStyles() {
    if (document.getElementById("hg-kp-styles")) return;
    const style = document.createElement("style");
    style.id = "hg-kp-styles";
    style.textContent = `
      .hg-kp-overlay {
        position: fixed; inset: 0; z-index: 400;
        background: rgba(16, 19, 17, 0.5);
        display: flex; align-items: center; justify-content: center;
        padding: 1rem;
      }
      .hg-kp-dialog {
        width: min(520px, 96vw);
        background: #fff;
        border-radius: 14px;
        border: 1px solid rgba(20,24,21,0.1);
        box-shadow: 0 24px 60px rgba(12,15,13,0.18);
        padding: 1.35rem 1.4rem 1.15rem;
        font-family: inherit;
        color: #171918;
      }
      .hg-kp-dialog h2 {
        margin: 0 0 0.35rem;
        font-size: 1.15rem;
        font-weight: 650;
        letter-spacing: -0.02em;
      }
      .hg-kp-dialog p.lead {
        margin: 0 0 1rem;
        color: #69706b;
        font-size: 0.9rem;
        line-height: 1.45;
      }
      .hg-kp-options { display: grid; gap: 0.65rem; margin-bottom: 1rem; }
      .hg-kp-option {
        display: block; width: 100%; text-align: left;
        border: 1px solid #dde1db; border-radius: 10px;
        background: #fafbf9; padding: 0.85rem 0.95rem;
        cursor: pointer; font: inherit; color: inherit;
        transition: border-color 0.15s ease, background 0.15s ease;
      }
      .hg-kp-option:hover, .hg-kp-option:focus {
        border-color: #2e7d57; background: rgba(118,161,132,0.1); outline: none;
      }
      .hg-kp-option strong { display: block; font-size: 0.95rem; margin-bottom: 0.2rem; }
      .hg-kp-option span { display: block; color: #69706b; font-size: 0.8rem; line-height: 1.4; }
      .hg-kp-option .badge {
        display: inline-block; margin-top: 0.4rem;
        font-size: 0.68rem; font-weight: 600; letter-spacing: 0.04em;
        text-transform: uppercase; color: #2e7d57;
        background: rgba(118,161,132,0.16); padding: 0.15rem 0.4rem; border-radius: 999px;
      }
      .hg-kp-option .badge.alt { color: #4a56b0; background: rgba(105,120,216,0.14); }
      .hg-kp-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
      .hg-kp-actions button {
        font: inherit; padding: 0.5rem 0.9rem; border-radius: 980px;
        border: 1px solid #dde1db; background: #fff; cursor: pointer;
      }
      .hg-kp-actions button:hover { background: #f0f2ef; }
    `;
    document.head.appendChild(style);
  }

  /**
   * @returns {Promise<'legacy'|'canonical'|null>}
   */
  function pickKnowledgePath(options) {
    const opts = options || {};
    ensureStyles();
    const pref = preferredPath();

    return new Promise((resolve) => {
      const existing = document.getElementById("hg-kp-overlay");
      if (existing) existing.remove();

      const overlay = document.createElement("div");
      overlay.id = "hg-kp-overlay";
      overlay.className = "hg-kp-overlay";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.setAttribute("aria-label", "Choose knowledge path");

      overlay.innerHTML = `
        <div class="hg-kp-dialog">
          <h2>${opts.title || "Choose knowledge path"}</h2>
          <p class="lead">${opts.subtitle || "Compare the production catalog path with the new canonical intervention graph. Same labs, different knowledge substrate."}</p>
          <div class="hg-kp-options">
            <button type="button" class="hg-kp-option" data-path="legacy">
              <strong>Legacy catalogs + evidence</strong>
              <span>Curated intervention catalogs, Tier A evidence claims, and live literature retrieval. Current production default.</span>
              <span class="badge">Recommended for clinical review</span>
            </button>
            <button type="button" class="hg-kp-option" data-path="canonical">
              <strong>Canonical graph registry</strong>
              <span>Routes only interventions present in canonical_entities with composition edges. Requires bootstrap. Experimental A/B path.</span>
              <span class="badge alt">Experimental · graph-backed</span>
            </button>
          </div>
          <div class="hg-kp-actions">
            <button type="button" data-action="cancel">Cancel</button>
          </div>
        </div>`;

      function close(value) {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        resolve(value);
      }

      function onKey(e) {
        if (e.key === "Escape") close(null);
      }

      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) close(null);
      });
      overlay.querySelector('[data-action="cancel"]').addEventListener("click", () => close(null));
      overlay.querySelectorAll("[data-path]").forEach((btn) => {
        if (btn.getAttribute("data-path") === pref) {
          btn.style.borderColor = "#2e7d57";
        }
        btn.addEventListener("click", () => {
          const path = btn.getAttribute("data-path");
          rememberPath(path);
          close(path);
        });
      });

      document.addEventListener("keydown", onKey);
      document.body.appendChild(overlay);
      const focusBtn = overlay.querySelector(`[data-path="${pref}"]`) || overlay.querySelector("[data-path]");
      if (focusBtn) focusBtn.focus();
    });
  }

  global.hgPickKnowledgePath = pickKnowledgePath;
  global.hgPreferredKnowledgePath = preferredPath;
})(typeof window !== "undefined" ? window : globalThis);
