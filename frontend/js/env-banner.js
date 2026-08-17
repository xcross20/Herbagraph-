/* Shows a non-production banner so UAT/preview is never mistaken for www.herbagraph.com. */
(function () {
  fetch("/meta", { credentials: "same-origin" })
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (meta) {
      if (!meta || meta.is_production) return;
      var bar = document.createElement("div");
      bar.id = "hg-env-banner";
      bar.setAttribute("role", "status");
      var label = meta.environment === "uat" ? "UAT" : (meta.environment || "preview");
      var sha = meta.git_sha ? " · " + meta.git_sha : "";
      bar.innerHTML =
        "<strong>" + label + "</strong> — synthetic demo data only. " +
        "<a href=\"/demo.html\">UAT home</a> · <a href=\"/app.html\">workspace</a>" + sha;
      document.body.prepend(bar);
    })
    .catch(function () { /* local pages without the API stay unmarked */ });
})();
