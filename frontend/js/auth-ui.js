/**
 * Shared auth page UI helpers (signup + login).
 */
window.HerbaGraphAuthUI = (function () {
  const PASSWORD_RULES = [
    { id: "len", test: (v) => v.length >= 8, label: "8 or more characters" },
    { id: "digit", test: (v) => /\d/.test(v), label: "One number" },
    { id: "upper", test: (v) => /[A-Z]/.test(v), label: "One uppercase letter" },
  ];

  function clearFieldErrors(root) {
    (root || document).querySelectorAll(".auth-field.is-invalid").forEach((el) => {
      el.classList.remove("is-invalid");
      const err = el.querySelector(".auth-field-error");
      if (err) err.remove();
    });
  }

  function showFieldError(fieldId, messageHtml) {
    const input = document.getElementById(fieldId);
    if (!input) return;
    const field = input.closest(".auth-field");
    if (!field) return;
    field.classList.add("is-invalid");
    let err = field.querySelector(".auth-field-error");
    if (!err) {
      err = document.createElement("p");
      err.className = "auth-field-error";
      err.setAttribute("role", "alert");
      field.appendChild(err);
    }
    err.innerHTML = messageHtml;
    input.setAttribute("aria-invalid", "true");
  }

  function clearFieldError(fieldId) {
    const input = document.getElementById(fieldId);
    if (!input) return;
    const field = input.closest(".auth-field");
    if (!field) return;
    field.classList.remove("is-invalid");
    const err = field.querySelector(".auth-field-error");
    if (err) err.remove();
    input.removeAttribute("aria-invalid");
  }

  function setBanner(el, message, kind) {
    if (!el) return;
    el.textContent = message;
    el.hidden = !message;
    el.className = kind === "ok" ? "auth-banner-success" : "auth-banner-error";
  }

  function setButtonLoading(btn, loading, loadingLabel) {
    if (!btn) return;
    if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = btn.textContent.trim();
    btn.disabled = loading;
    if (loading) {
      btn.innerHTML = `<span class="auth-spinner" aria-hidden="true"></span>${loadingLabel || "Please wait…"}`;
    } else {
      btn.textContent = btn.dataset.defaultLabel;
    }
  }

  function initPasswordField(inputId, rulesListId) {
    const input = document.getElementById(inputId);
    const list = document.getElementById(rulesListId);
    const toggle = document.querySelector(`[data-toggle-for="${inputId}"]`);
    if (!input) return;

    if (toggle) {
      toggle.addEventListener("click", () => {
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        toggle.textContent = show ? "Hide" : "Show";
        toggle.setAttribute("aria-pressed", show ? "true" : "false");
      });
    }

    if (!list) return;

    const items = PASSWORD_RULES.map((rule) => {
      const li = document.createElement("li");
      li.dataset.rule = rule.id;
      li.textContent = rule.label;
      list.appendChild(li);
      return { rule, li };
    });

    const refresh = () => {
      const value = input.value || "";
      items.forEach(({ rule, li }) => {
        li.classList.toggle("is-met", rule.test(value));
      });
    };

    input.addEventListener("input", refresh);
    refresh();
  }

  function passwordMeetsRequirements(value) {
    return PASSWORD_RULES.every((r) => r.test(value || ""));
  }

  function getSelectedAccountRole() {
    const checked = document.querySelector('input[name="account-type"]:checked');
    return checked ? checked.value : "individual";
  }

  function initAccountTypeSelector() {
    document.querySelectorAll('input[name="account-type"]').forEach((radio) => {
      radio.addEventListener("change", () => clearFieldError("account-type-group"));
    });
  }

  async function playWorkspaceReady(callback) {
    const overlay = document.getElementById("auth-success-overlay");
    if (!overlay) {
      if (callback) await callback();
      return;
    }
    const steps = overlay.querySelectorAll(".auth-success-steps li");
    overlay.hidden = false;
    for (let i = 0; i < steps.length; i += 1) {
      steps[i].classList.add("is-done");
      await new Promise((r) => setTimeout(r, 380));
    }
    await new Promise((r) => setTimeout(r, 280));
    if (callback) await callback();
  }

  function configureAccessCodeField(required) {
    const wrap = document.getElementById("auth-access-wrap");
    const input = document.getElementById("auth-access-code");
    if (!wrap || !input) return;
    wrap.hidden = !required;
    input.required = required;
  }

  return {
    PASSWORD_RULES,
    clearFieldErrors,
    showFieldError,
    clearFieldError,
    setBanner,
    setButtonLoading,
    initPasswordField,
    passwordMeetsRequirements,
    getSelectedAccountRole,
    initAccountTypeSelector,
    playWorkspaceReady,
    configureAccessCodeField,
  };
})();