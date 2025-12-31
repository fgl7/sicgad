document.addEventListener("DOMContentLoaded", function () {
  const btn = document.getElementById("download-template-btn");
  const select = document.getElementById("id_dataset_type");
  let datasetMeta = null;
  if (btn && select) {
    const url = btn.getAttribute("data-download-url");
    if (url) {
      btn.addEventListener("click", function () {
        const value = select.value;
        if (!value) {
          alert("Primero selecciona un tipo de dataset para generar la plantilla.");
          return;
        }

        const target = url + "?dataset_type=" + encodeURIComponent(value);
        window.location.href = target;
      });
    }
  }

  const hint = document.getElementById("dataset-validation-hint");
  if (hint) {
    const updateHint = function () {
      if (datasetMeta && datasetMeta.validation_frequency) {
        const freq = String(datasetMeta.validation_frequency || "").toUpperCase();
        const isCertification = Boolean(datasetMeta.is_certification);

        if (isCertification && freq === "MONTHLY") {
          hint.textContent =
            "Este dataset es de certificacion mensual. Al enviarlo se genera una consolidacion automatica.";
          return;
        }
        if (freq === "DAILY") {
          hint.textContent =
            "Este dataset se valida de forma diaria. Recuerda enviarlo despues de cargarlo.";
          return;
        }
        if (freq === "WEEKLY") {
          hint.textContent =
            "Este dataset se valida de forma semanal. Recuerda enviarlo despues de cargarlo.";
          return;
        }
        if (freq === "MONTHLY") {
          hint.textContent =
            "Este dataset se valida de forma mensual. Recuerda enviarlo despues de cargarlo.";
          return;
        }
        if (freq === "FLEXIBLE") {
          hint.textContent =
            "Este dataset es de proyecciones (periodicidad no definida). Se valida con el flujo mensual.";
          return;
        }
      }

      hint.textContent = "";
    };

    updateHint();
    select.addEventListener("change", updateHint);
  }

  const importLink = document.getElementById("import-historical-link");
  const dailyWrapper = document.getElementById("daily-upload-wrapper");
  const requiredBanner = document.getElementById("historical-required-banner");

  function setHistoricalRequired(required) {
    if (!importLink || !dailyWrapper || !requiredBanner) {
      return;
    }

    if (required) {
      requiredBanner.classList.remove("hidden");
      dailyWrapper.classList.add(
        "opacity-40",
        "blur-[1px]",
        "pointer-events-none",
        "select-none"
      );

      importLink.classList.remove("hidden");
      importLink.textContent = "Importar histórico";
      importLink.classList.remove(
        "pointer-events-none",
        "opacity-60",
        "bg-slate-800",
        "text-slate-300"
      );
      importLink.classList.add("bg-fuchsia-600", "hover:bg-fuchsia-500", "animate-pulse");
      importLink.setAttribute("title", "Importa el histórico para habilitar la carga diaria");
      return;
    }

    requiredBanner.classList.add("hidden");
    dailyWrapper.classList.remove(
      "opacity-40",
      "blur-[1px]",
      "pointer-events-none",
      "select-none"
    );

    importLink.classList.add("hidden");
    importLink.classList.remove("animate-pulse", "bg-fuchsia-600", "hover:bg-fuchsia-500");
    importLink.classList.remove("pointer-events-none", "opacity-60", "bg-slate-800", "text-slate-300");
    importLink.setAttribute("title", "");
  }

  function getPlantId() {
    const hiddenPlant = document.querySelector('input[name="plant"]');
    if (hiddenPlant && hiddenPlant.value) {
      return hiddenPlant.value;
    }
    const plantSelect = document.getElementById("id_plant");
    return plantSelect ? plantSelect.value : "";
  }

  function refreshHistoricalGate() {
    if (!importLink || !select) {
      return;
    }
    const hasDataUrl = importLink.getAttribute("data-has-data-url");
    if (!hasDataUrl) {
      return;
    }
    const datasetTypeId = select.value;

    // Si aún no se eligió dataset, no bloqueamos la UI (el usuario necesita poder seleccionarlo),
    // y mantenemos oculta la opción de importar histórico hasta que se seleccione un dataset.
    if (!datasetTypeId) {
      datasetMeta = null;
      if (hint) {
        hint.textContent = "";
      }
      if (requiredBanner) {
        requiredBanner.classList.add("hidden");
      }
      if (dailyWrapper) {
        dailyWrapper.classList.remove(
          "opacity-40",
          "blur-[1px]",
          "pointer-events-none",
          "select-none"
        );
      }
      if (importLink) {
        importLink.classList.add("hidden");
        importLink.setAttribute("title", "");
      }
      return;
    }

    fetch(hasDataUrl + "?dataset_type=" + encodeURIComponent(datasetTypeId))
      .then((resp) => (resp.ok ? resp.json() : { has_data: false }))
      .then((data) => {
        const hasData = data && data.has_data;
        datasetMeta = data || null;
        select.dispatchEvent(new Event("change"));

        const freq = String((data && data.validation_frequency) || "").toUpperCase();
        const requiresHistorical = freq === "DAILY";
        setHistoricalRequired(requiresHistorical && !hasData);
      })
      .catch(() => {
        datasetMeta = null;
        select.dispatchEvent(new Event("change"));
        setHistoricalRequired(true);
      });
  }

  if (importLink && dailyWrapper && requiredBanner && select) {
    refreshHistoricalGate();
    select.addEventListener("change", refreshHistoricalGate);
    const plantSelect = document.getElementById("id_plant");
    if (plantSelect) {
      plantSelect.addEventListener("change", refreshHistoricalGate);
    }
  }
});
