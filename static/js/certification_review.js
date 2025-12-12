document.addEventListener("DOMContentLoaded", function () {
  const scopes = document.querySelectorAll("[data-cert-scope]");

  scopes.forEach(function (scope) {
    const canEdit = scope.getAttribute("data-can-edit") === "true";
    if (!canEdit) {
      return;
    }

    const justificationInput = scope.querySelector("[data-justification-input]");
    if (!justificationInput) {
      return;
    }

    const editableFields = scope.querySelectorAll('[data-requires-justification="true"]');
    const supportInputs = scope.querySelectorAll("[data-support-input='true']");
    const activateButton = scope.querySelector("[data-activate-justification]");
    const submitButtons = scope.querySelectorAll("[data-submit-when-ready='true']");
    const autoActivate = scope.getAttribute("data-auto-activate") === "true";

    function currentReady() {
      return scope.getAttribute("data-justification-ready") === "true";
    }

    function setReady(state) {
      scope.setAttribute("data-justification-ready", state ? "true" : "false");
    }

    function updateState() {
      const hasText = justificationInput.value.trim().length > 0;
      if (autoActivate) {
        setReady(hasText);
      }
      const ready = currentReady();

      editableFields.forEach(function (field) {
        field.disabled = !ready;
      });

      supportInputs.forEach(function (input) {
        if (autoActivate) {
          input.disabled = !hasText;
        } else {
          input.disabled = !hasText && !ready;
        }
      });

      if (activateButton) {
        activateButton.disabled = !hasText;
      }

      submitButtons.forEach(function (button) {
        button.disabled = !ready;
      });
    }

    updateState();
    justificationInput.addEventListener("input", updateState);

    if (!autoActivate && activateButton) {
      activateButton.addEventListener("click", function () {
        if (!justificationInput.value.trim()) {
          const errorHolder = scope.querySelector("[data-justification-error]");
          if (errorHolder) {
            errorHolder.textContent = "Debes ingresar la justificacion antes de habilitar la edicion.";
            errorHolder.classList.remove("hidden");
          }
          return;
        }
        const errorHolder = scope.querySelector("[data-justification-error]");
        if (errorHolder) {
          errorHolder.classList.add("hidden");
        }
        setReady(true);
        updateState();
      });
    }
  });

  const modal = document.getElementById("daily-edit-modal");
  if (!modal) {
    return;
  }
  const modalContent = document.getElementById("daily-edit-modal-content");
  const modalTitle = document.getElementById("daily-edit-modal-title");
  let activeHolder = null;

  function closeModal() {
    if (modal.classList.contains("hidden")) {
      return;
    }
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    if (activeHolder) {
      const form = modalContent.querySelector("form");
      if (form) {
        form.classList.add("hidden");
        activeHolder.appendChild(form);
      }
      activeHolder = null;
    }
  }

  document.querySelectorAll("[data-open-daily-modal]").forEach(function (button) {
    button.addEventListener("click", function () {
      const targetKey = button.getAttribute("data-target-key");
      const holder = document.querySelector("[data-daily-holder='" + targetKey + "']");
      if (!holder) {
        return;
      }
      const form = holder.querySelector("form");
      if (!form) {
        return;
      }

      if (!modal.classList.contains("hidden")) {
        closeModal();
      }

      activeHolder = holder;
      const label = button.getAttribute("data-period-label") || targetKey || "";
      modalTitle.textContent = "Dia " + label;
      modalContent.innerHTML = "";
      modalContent.appendChild(form);
      form.classList.remove("hidden");
      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");
    });
  });

  modal.querySelectorAll("[data-close-daily-modal]").forEach(function (button) {
    button.addEventListener("click", closeModal);
  });

  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      closeModal();
    }
  });

  const autoOpenForm = document.querySelector("[data-daily-form][data-open-on-load='true']");
  if (autoOpenForm) {
    const targetKey = autoOpenForm.getAttribute("data-daily-id");
    const trigger = document.querySelector("[data-open-daily-modal][data-target-key='" + targetKey + "']");
    if (trigger) {
      trigger.click();
    } else {
      activeHolder = autoOpenForm.parentElement || null;
      modalContent.innerHTML = "";
      modalContent.appendChild(autoOpenForm);
      autoOpenForm.classList.remove("hidden");
      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");
    }
  }
});
