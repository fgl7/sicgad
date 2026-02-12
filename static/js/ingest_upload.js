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
  if (hint && select) {
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
      importLink.textContent = "Importar historico";
      importLink.classList.remove(
        "pointer-events-none",
        "opacity-60",
        "bg-slate-800",
        "text-slate-300"
      );
      importLink.classList.add("bg-fuchsia-600", "hover:bg-fuchsia-500", "animate-pulse");
      importLink.setAttribute("title", "Importa el historico para habilitar la carga periodica");
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

  function refreshHistoricalGate() {
    if (!importLink || !select) {
      return;
    }

    const hasDataUrl = importLink.getAttribute("data-has-data-url");
    if (!hasDataUrl) {
      return;
    }

    const datasetTypeId = select.value;
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
        const requiresHistorical = ["DAILY", "WEEKLY", "MONTHLY"].includes(freq);
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
  }

  const historicalForm = document.getElementById("historical-upload-form");
  const historicalStatus = document.getElementById("historical-upload-status");
  const historicalStatusText = document.getElementById("historical-upload-status-text");
  const historicalPercent = document.getElementById("historical-upload-percent");
  const historicalProgress = document.getElementById("historical-upload-progress");
  const historicalSubmit = document.getElementById("historical-upload-submit");
  const historicalBackendPhase = document.getElementById("historical-upload-backend-phase");
  const historicalBackendText = document.getElementById("historical-upload-backend-text");

  if (
    historicalForm &&
    historicalStatus &&
    historicalStatusText &&
    historicalPercent &&
    historicalProgress &&
    historicalSubmit &&
    historicalBackendPhase &&
    historicalBackendText
  ) {
    let inFlight = false;

    const setProgress = function (percent, message) {
      const safe = Math.max(0, Math.min(100, percent));
      historicalPercent.textContent = safe + "%";
      historicalProgress.style.width = safe + "%";
      historicalStatusText.textContent = message;
    };

    const setBackendPhase = function (active, message) {
      if (active) {
        historicalBackendPhase.classList.remove("hidden");
      } else {
        historicalBackendPhase.classList.add("hidden");
      }
      historicalBackendText.textContent = message || "Procesando historico en servidor...";
    };

    const setFormDisabled = function (disabled) {
      const controls = historicalForm.querySelectorAll("input, select, textarea, button");
      controls.forEach((control) => {
        control.disabled = disabled;
      });
    };

    historicalForm.addEventListener("submit", function (event) {
      if (inFlight) {
        event.preventDefault();
        return;
      }

      if (!historicalForm.checkValidity()) {
        return;
      }

      if (!window.XMLHttpRequest) {
        historicalStatus.classList.remove("hidden");
        setProgress(5, "Iniciando carga...");
        return;
      }

      event.preventDefault();
      inFlight = true;

      historicalStatus.classList.remove("hidden");
      setProgress(0, "Preparando archivo...");
      setBackendPhase(false, "");
      setFormDisabled(true);

      const xhr = new XMLHttpRequest();
      const action = historicalForm.getAttribute("action") || window.location.href;
      const method = (historicalForm.getAttribute("method") || "POST").toUpperCase();

      xhr.open(method, action, true);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");

      xhr.upload.addEventListener("progress", function (progressEvent) {
        setBackendPhase(false, "");
        if (progressEvent.lengthComputable && progressEvent.total > 0) {
          const rawPercent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          const capped = Math.min(99, rawPercent);
          setProgress(capped, "Subiendo archivo...");
        } else {
          setProgress(15, "Subiendo archivo...");
        }
      });

      xhr.upload.addEventListener("loadend", function () {
        if (inFlight) {
          setProgress(99, "Archivo recibido. Procesando historico...");
          setBackendPhase(true, "Procesando historico en servidor...");
        }
      });

      xhr.addEventListener("load", function () {
        if (xhr.status >= 200 && xhr.status < 400) {
          setProgress(100, "Carga completada. Redirigiendo...");
          setBackendPhase(true, "Proceso completado.");
          window.location.href = xhr.responseURL || action;
          return;
        }

        setProgress(0, "No se pudo completar la importacion. Revisa el formulario.");
        setBackendPhase(false, "");
        setFormDisabled(false);
        inFlight = false;
      });

      xhr.addEventListener("error", function () {
        setProgress(0, "Error de red durante la carga. Intenta nuevamente.");
        setBackendPhase(false, "");
        setFormDisabled(false);
        inFlight = false;
      });

      xhr.addEventListener("abort", function () {
        setProgress(0, "La carga fue cancelada.");
        setBackendPhase(false, "");
        setFormDisabled(false);
        inFlight = false;
      });

      setTimeout(function () {
        const currentProgress = Number.parseInt(historicalPercent.textContent || "0", 10);
        if (inFlight && currentProgress >= 95) {
          setBackendPhase(true, "Procesando historico en servidor...");
        }
      }, 1200);

      xhr.send(new FormData(historicalForm));
    });
  }
});
