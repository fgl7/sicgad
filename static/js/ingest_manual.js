document.addEventListener("DOMContentLoaded", function () {
  const datasetSelect = document.getElementById("id_dataset_type");
  const periodInput = document.getElementById("id_period");

  if (datasetSelect) {
    datasetSelect.addEventListener("change", function () {
      const value = this.value;
      if (!value) {
        return;
      }
      const url = new URL(window.location.href);
      url.searchParams.set("dataset_type", value);
      url.searchParams.set("rows", url.searchParams.get("rows") || "1");
      window.location.href = url.toString();
    });
  }

  function syncFirstRowDate() {
    if (!periodInput) {
      return;
    }
    const value = periodInput.value;
    if (!value) {
      return;
    }
    const firstDateField = document.querySelector(
      'input[data-manual-date-field="true"][name^="rows-0-"]'
    );
    if (firstDateField) {
      firstDateField.value = value;
    }
  }

  if (periodInput) {
    periodInput.addEventListener("change", syncFirstRowDate);
    periodInput.addEventListener("blur", syncFirstRowDate);
    syncFirstRowDate();
  }
});
