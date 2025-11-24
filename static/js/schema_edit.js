document.addEventListener("DOMContentLoaded", function () {
  const addBtn = document.getElementById("add-column-btn");
  const tbody = document.getElementById("columns-body");
  const template = document.getElementById("empty-column-row");
  const totalFormsInput = document.querySelector("[data-schema-columns-total-forms]");

  if (!addBtn || !tbody || !template || !totalFormsInput) {
    return;
  }

  function renumberDisplayOrder() {
    const rows = tbody.querySelectorAll("tr[data-column-row]");
    let order = 1;

    rows.forEach(function (row) {
      if (row.classList.contains("is-deleted")) {
        return;
      }
      const orderField = row.querySelector("[name$='-display_order']");
      if (orderField) {
        orderField.value = order;
        try {
          orderField.readOnly = true;
        } catch (e) {
          // ignorar si el campo no soporta readOnly
        }
        order += 1;
      }
    });
  }

  tbody.addEventListener("click", function (event) {
    const deleteBtn = event.target.closest("[data-delete-row]");
    if (!deleteBtn) {
      return;
    }

    const row = deleteBtn.closest("tr[data-column-row]");
    if (!row) {
      return;
    }

    const deleteInput = row.querySelector("[name$='-DELETE']");
    if (deleteInput) {
      deleteInput.checked = true;
      deleteInput.value = "on";
    }

    row.classList.add("is-deleted", "hidden");
    renumberDisplayOrder();
  });

  // Marcar cuando el usuario edita manualmente la etiqueta
  tbody.addEventListener("input", function (event) {
    const target = event.target;

    // Si el usuario escribe en "Etiqueta", dejamos de sobreescribirla.
    if (target.matches("input[name$='-label']")) {
      target.dataset.manualEdited = "1";
      return;
    }

    // Copiar automáticamente "Nombre" en "Etiqueta" mientras no haya sido editada.
    if (!target.matches("input[name$='-name']")) {
      return;
    }

    const row = target.closest("tr[data-column-row]");
    if (!row) {
      return;
    }

    const labelInput = row.querySelector("input[name$='-label']");
    if (!labelInput) {
      return;
    }

    if (labelInput.dataset.manualEdited === "1") {
      return;
    }

    labelInput.value = target.value;
  });

  addBtn.addEventListener("click", function () {
    const currentCount = parseInt(totalFormsInput.value || "0", 10);
    const newIndex = currentCount;

    const clone = template.content.cloneNode(true);
    const regex = new RegExp("__prefix__", "g");

    clone.querySelectorAll("input, select, textarea, label").forEach(function (el) {
      if (el.name) {
        el.name = el.name.replace(regex, newIndex);
      }
      if (el.id) {
        el.id = el.id.replace(regex, newIndex);
      }
      if (el.htmlFor) {
        el.htmlFor = el.htmlFor.replace(regex, newIndex);
      }
    });

    tbody.appendChild(clone);
    totalFormsInput.value = newIndex + 1;
    renumberDisplayOrder();
  });

  renumberDisplayOrder();
});
