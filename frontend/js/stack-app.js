(function () {
  const MARKERS = [["LDL", "mg/dL"], ["HDL", "mg/dL"], ["Triglycerides", "mg/dL"], ["Glucose", "mg/dL"], ["HbA1c", "%"], ["ALT", "U/L"], ["AST", "U/L"]];

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function listOrNull(value) {
    const items = value.split(",").map(function (part) { return part.trim(); }).filter(Boolean);
    return items.length ? items : null;
  }

  const grid = document.getElementById("lab-grid");
  MARKERS.forEach(function (pair) {
    const name = pair[0];
    const unit = pair[1];
    const wrap = document.createElement("label");
    wrap.append(document.createTextNode(name));
    const input = document.createElement("input");
    input.setAttribute("data-lab", name);
    input.setAttribute("data-unit", unit);
    input.setAttribute("inputmode", "decimal");
    input.placeholder = unit;
    wrap.append(input);
    grid.appendChild(wrap);
  });

  function accessToken() {
    if (window.hgToken) return window.hgToken;
    try {
      const stored = JSON.parse(localStorage.getItem("hg_tokens") || "null");
      return stored && stored.access_token;
    } catch (err) {
      return null;
    }
  }

  document.getElementById("stack-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    const labs = Array.from(document.querySelectorAll("[data-lab]")).map(function (el) {
      return {
        name: el.getAttribute("data-lab"),
        value: el.value,
        unit: el.getAttribute("data-unit"),
      };
    }).filter(function (row) { return row.value !== ""; }).map(function (row) {
      return { name: row.name, value: Number(row.value), unit: row.unit };
    });
    const stack = listOrNull(document.getElementById("stack-items").value) || [];
    const medications = listOrNull(document.getElementById("stack-meds").value);
    const conditions = listOrNull(document.getElementById("stack-conds").value);
    const receipt = document.getElementById("stack-receipt");
    receipt.hidden = false;
    receipt.textContent = "Checking…";
    const token = accessToken();
    const headers = { "Content-Type": "application/json" };
    if (token) headers.Authorization = "Bearer " + token;
    const resp = await fetch(token ? "/api/v1/cases/stack-check" : "/api/v1/public/stack-check", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ labs: labs, stack: stack, medications: medications, conditions: conditions }),
    });
    const data = await resp.json().catch(function () { return {}; });
    if (!resp.ok) {
      receipt.innerHTML = '<p class="error">' + esc(data.detail || "Could not check that stack.") + "</p>";
      return;
    }
    const colors = { hold: "#8C3A3A", food_first: "#1F6B4A", discuss: "#1F4E79", mismatch: "#5C6560", unknown: "#5C6560" };
    const rows = (data.verdicts || []).map(function (row) {
      const extra = row.next_clarification ? "<br><span class=\"muted\">" + esc(row.next_clarification) + "</span>" : "";
      return "<p><strong style=\"color:" + (colors[row.verdict] || "#1A1F1C") + "\">" + esc(String(row.verdict || "").toUpperCase()) + "</strong> " + esc(row.name) + " — " + esc(row.reason) + extra + "</p>";
    }).join("");
    const saved = data.case_id
      ? '<p><a href="/case-report.html?case=' + encodeURIComponent(data.case_id) + '">Open the saved report</a></p>'
      : "";
    receipt.innerHTML = '<div class="app-card" style="padding:1.25rem"><h2>Receipt</h2>' + rows + '<p class="muted">' + esc(data.disclaimer) + "</p>" + saved + '<p><a href="/ask.html">A longer unexplained illness belongs in Ask, not here.</a></p></div>';
  });
})();
