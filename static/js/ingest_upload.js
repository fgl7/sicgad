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
});

