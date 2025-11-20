document.addEventListener("DOMContentLoaded", function () {
  const addBtn = document.getElementById("add-column-btn");
  const tbody = document.getElementById("columns-body");
  const template = document.getElementById("empty-column-row");
  const totalFormsInput = document.querySelector("[data-schema-columns-total-forms]");

  if (!addBtn || !tbody || !template || !totalFormsInput) {
    return;
  }

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
  });
});

