(function () {
  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function accessToken() {
    if (window.hgToken) return window.hgToken;
    try {
      const stored = JSON.parse(localStorage.getItem("hg_tokens") || "null");
      return stored && stored.access_token;
    } catch (err) {
      return null;
    }
  }

  const mount = document.getElementById("case-report");
  const caseId = new URLSearchParams(location.search).get("case");
  const token = accessToken();
  if (!caseId) {
    mount.textContent = "This page needs the case link from your stack check.";
    return;
  }
  if (!token) {
    mount.textContent = "Sign in to read a saved report.";
    return;
  }

  fetch("/api/v1/cases/" + encodeURIComponent(caseId) + "/report", {
    headers: { Authorization: "Bearer " + token },
  }).then(function (resp) {
    return resp.json().then(function (data) {
      return { ok: resp.ok, status: resp.status, data: data };
    });
  }).then(function (result) {
    if (!result.ok) {
      mount.textContent = result.status === 404
        ? "That report is not on this account."
        : "Could not read that report.";
      return;
    }
    const data = result.data || {};
    const labs = (data.labs || []).map(function (row) {
      return "<p>" + esc(row.text) + "</p>";
    }).join("");
    const items = (data.items || []).map(function (row) {
      return "<p><strong>" + esc(String(row.verdict || "").toUpperCase()) + "</strong> "
        + esc(row.name) + " — " + esc(row.text) + "</p>";
    }).join("");
    const empty = items ? "" : "<p>No stack check is saved on this case.</p>";
    mount.innerHTML = labs + empty + items + '<p class="muted">' + esc(data.disclaimer) + "</p>";
  }).catch(function () {
    mount.textContent = "Could not read that report.";
  });
})();
