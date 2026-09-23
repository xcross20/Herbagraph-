(function () {
  const MARKERS = [["LDL","mg/dL"],["HDL","mg/dL"],["Triglycerides","mg/dL"],["Glucose","mg/dL"],["HbA1c","%"],["ALT","U/L"],["AST","U/L"]];
  const grid = document.getElementById("lab-grid");
  MARKERS.forEach(([name, unit]) => {
    const wrap = document.createElement("label");
    wrap.innerHTML = name + '<input data-lab="' + name + '" data-unit="' + unit + '" inputmode="decimal" placeholder="' + unit + '">';
    grid.appendChild(wrap);
  });
  const params = new URLSearchParams(location.search);
  if (params.get("demo") === "1") {
    const demo = { LDL: 162, HDL: 38, Triglycerides: 210, Glucose: 102, HbA1c: 5.8, ALT: 22, AST: 24 };
    Object.entries(demo).forEach(([k, v]) => { const el = document.querySelector('[data-lab="' + k + '"]'); if (el) el.value = v; });
    document.getElementById("stack-items").value = "Berberine, Red yeast rice";
    document.getElementById("stack-meds").value = "Crestor";
  }
  document.getElementById("stack-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const labs = [...document.querySelectorAll("[data-lab]")].map((el) => ({ name: el.getAttribute("data-lab"), value: el.value, unit: el.getAttribute("data-unit") })).filter((row) => row.value !== "").map((row) => ({ name: row.name, value: Number(row.value), unit: row.unit }));
    const stack = document.getElementById("stack-items").value.split(",").map((s) => s.trim()).filter(Boolean);
    const medications = document.getElementById("stack-meds").value.split(",").map((s) => s.trim()).filter(Boolean);
    const conditions = document.getElementById("stack-conds").value.split(",").map((s) => s.trim()).filter(Boolean);
    const receipt = document.getElementById("stack-receipt");
    receipt.hidden = false;
    receipt.innerHTML = "<p>Checking…</p>";
    const resp = await fetch("/api/v1/public/stack-check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ labs, stack, medications, conditions, ranking_mode: "consumer" }) });
    const data = await resp.json();
    if (!resp.ok) { receipt.innerHTML = '<p class="error">' + (data.detail || "Could not check that stack.") + "</p>"; return; }
    const colors = { hold: "#b42318", food_first: "#2f6f4e", discuss: "#1f4b99", mismatch: "#6f6a62", unknown: "#6f6a62" };
    receipt.innerHTML = '<div class="app-card" style="padding:1.25rem"><h2>Receipt</h2>' + (data.verdicts || []).map((row) => '<p><strong style="color:' + (colors[row.verdict] || '#171918') + '">' + row.verdict.toUpperCase() + '</strong> ' + row.name + ' — ' + row.reason + '</p>').join('') + ((data.clinician_questions || []).length ? '<h3>Ask your clinician</h3><ul>' + data.clinician_questions.map((q) => '<li>' + q + '</li>').join('') + '</ul>' : '') + '<p class="muted">' + data.disclaimer + '</p><p class="muted">Follow-up: same markers in ' + data.follow_up.window_weeks + ' weeks. Movement is not causation.</p><p><a href="/ask.html">Need investigation of a longer story? Open Ask.</a></p></div>';
  });
})();
