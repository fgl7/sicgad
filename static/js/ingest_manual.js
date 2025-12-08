document.addEventListener("DOMContentLoaded", function () {
  const datasetSelect = document.getElementById("id_dataset_type");
  if (!datasetSelect) {
    return;
  }

  datasetSelect.addEventListener("change", function () {
    const value = this.value;
    if (!value) {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("dataset_type", value);
    const rows = url.searchParams.get("rows");
    if (!rows) {
      url.searchParams.set("rows", "5");
    }
    window.location.href = url.toString();
  });
});
