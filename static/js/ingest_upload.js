document.addEventListener("DOMContentLoaded", function () {
  const btn = document.getElementById("download-template-btn");
  if (!btn) {
    return;
  }

  const select = document.getElementById("id_dataset_type");
  const url = btn.getAttribute("data-download-url");

  if (!select || !url) {
    return;
  }

  btn.addEventListener("click", function () {
    const value = select.value;
    if (!value) {
      alert("Primero selecciona un tipo de dataset para generar la plantilla.");
      return;
    }

    const target = url + "?dataset_type=" + encodeURIComponent(value);
    window.location.href = target;
  });

  const hint = document.getElementById("dataset-validation-hint");
  if (hint) {
    const normalizeText = function (text) {
      return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    };

    const updateHint = function () {
      const option = select.options[select.selectedIndex];
      if (!option) {
        hint.textContent = "";
        return;
      }
      const label = normalizeText(option.textContent.toLowerCase());
      if (label.includes("certificacion")) {
        hint.textContent =
          "Este dataset es de certificacion mensual. Al enviarlo se genera una consolidacion automatica.";
      } else {
        hint.textContent =
          "Este dataset se valida de forma diaria. Recuerda enviarlo despues de cargarlo.";
      }
    };

    updateHint();
    select.addEventListener("change", updateHint);
  }
});
