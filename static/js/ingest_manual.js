document.addEventListener("DOMContentLoaded", function () {
  const datasetSelect = document.getElementById("id_dataset_type");
  const periodInput = document.getElementById("id_period");
  const manualForm = document.querySelector("form[data-month-lock]");
  const monthLockEnabled = manualForm && manualForm.dataset.monthLock === "true";

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

  function applyMonthLock() {
    if (!monthLockEnabled || !periodInput) {
      return;
    }
    const value = periodInput.value;
    if (!value) {
      return;
    }
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) {
      return;
    }
    const targetMonth = parsed.getMonth() + 1;
    const monthInputs = document.querySelectorAll("[data-month-number]");
    monthInputs.forEach((input) => {
      const inputMonth = Number(input.dataset.monthNumber || 0);
      if (!inputMonth) {
        return;
      }
      const shouldDisable = inputMonth !== targetMonth;
      input.disabled = shouldDisable;
      input.classList.toggle("opacity-40", shouldDisable);
    });
  }

  if (periodInput) {
    periodInput.addEventListener("change", syncFirstRowDate);
    periodInput.addEventListener("blur", syncFirstRowDate);
    syncFirstRowDate();
    periodInput.addEventListener("change", applyMonthLock);
    periodInput.addEventListener("blur", applyMonthLock);
    applyMonthLock();
  }
});
