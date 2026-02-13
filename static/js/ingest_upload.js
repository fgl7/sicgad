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
  const historicalModal = document.getElementById("historical-upload-modal");
  const historicalStatusText = document.getElementById("historical-upload-status-text");
  const historicalPercent = document.getElementById("historical-upload-percent");
  const historicalProgress = document.getElementById("historical-upload-progress");
  const historicalSubmit = document.getElementById("historical-upload-submit");
  const historicalBackendPhase = document.getElementById("historical-upload-backend-phase");
  const historicalBackendText = document.getElementById("historical-upload-backend-text");
  const historicalCancel = document.getElementById("historical-upload-cancel");

  if (
    historicalForm &&
    historicalModal &&
    historicalStatusText &&
    historicalPercent &&
    historicalProgress &&
    historicalSubmit &&
    historicalBackendPhase &&
    historicalBackendText &&
    historicalCancel
  ) {
    let inFlight = false;
    let activeXhr = null;
    let pollingTimer = null;
    let currentBatchProgressUrl = "";
    let currentBatchCancelUrl = "";

    const openModal = function () {
      historicalModal.classList.remove("hidden");
      document.body.classList.add("overflow-hidden");
    };

    const closeModal = function () {
      historicalModal.classList.add("hidden");
      document.body.classList.remove("overflow-hidden");
    };

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
        if (control.name === "csrfmiddlewaretoken") {
          return;
        }
        control.disabled = disabled;
      });
    };

    const stopPolling = function () {
      if (pollingTimer) {
        window.clearTimeout(pollingTimer);
        pollingTimer = null;
      }
    };

    const resetInFlight = function () {
      inFlight = false;
      activeXhr = null;
      currentBatchProgressUrl = "";
      currentBatchCancelUrl = "";
      setFormDisabled(false);
    };

    const pollBatchProgress = function (fallbackRedirectUrl) {
      if (!currentBatchProgressUrl || !inFlight) {
        return;
      }

      fetch(currentBatchProgressUrl, {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then((resp) => (resp.ok ? resp.json() : null))
        .then((data) => {
          if (!data) {
            throw new Error("Sin respuesta de progreso");
          }

          if (typeof data.percent === "number") {
            setProgress(data.percent, data.message || "Procesando historico en servidor...");
          }

          if (data.status === "DONE") {
            setProgress(100, "Carga completada. Redirigiendo...");
            setBackendPhase(true, "Proceso completado.");
            historicalCancel.disabled = true;
            stopPolling();
            const target = data.redirect_url || fallbackRedirectUrl || window.location.href;
            window.setTimeout(function () {
              window.location.href = target;
            }, 250);
            return;
          }

          if (data.status === "FAILED") {
            setProgress(0, data.error || data.message || "El proceso historico fallo.");
            setBackendPhase(false, "");
            stopPolling();
            resetInFlight();
            return;
          }

          setBackendPhase(true, "Procesando historico en servidor...");
          pollingTimer = window.setTimeout(function () {
            pollBatchProgress(fallbackRedirectUrl);
          }, 1000);
        })
        .catch(function () {
          pollingTimer = window.setTimeout(function () {
            pollBatchProgress(fallbackRedirectUrl);
          }, 1500);
        });
    };

    historicalCancel.addEventListener("click", function () {
      if (activeXhr && inFlight) {
        activeXhr.abort();
        return;
      }

      if (inFlight && currentBatchCancelUrl) {
        const csrfInput = historicalForm.querySelector('input[name="csrfmiddlewaretoken"]');
        const csrfToken = csrfInput ? csrfInput.value : "";
        fetch(currentBatchCancelUrl, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrfToken,
          },
        }).finally(function () {
          stopPolling();
          setProgress(0, "Proceso cancelado por el usuario.");
          setBackendPhase(false, "");
          resetInFlight();
          closeModal();
        });
        return;
      }

      closeModal();
    });

    historicalForm.addEventListener("submit", function (event) {
      if (inFlight) {
        event.preventDefault();
        return;
      }

      if (!historicalForm.checkValidity()) {
        return;
      }

      if (!window.XMLHttpRequest) {
        openModal();
        setProgress(5, "Iniciando carga...");
        return;
      }

      event.preventDefault();
      inFlight = true;
      stopPolling();
      const formData = new FormData(historicalForm);
      const csrfToken = (formData.get("csrfmiddlewaretoken") || "").toString();

      openModal();
      setProgress(0, "Preparando archivo...");
      setBackendPhase(false, "");
      setFormDisabled(true);
      historicalCancel.disabled = false;

      const xhr = new XMLHttpRequest();
      activeXhr = xhr;

      const action = historicalForm.getAttribute("action") || window.location.href;
      const method = (historicalForm.getAttribute("method") || "POST").toUpperCase();

      xhr.open(method, action, true);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      if (csrfToken) {
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
      }

      xhr.upload.addEventListener("progress", function (progressEvent) {
        setBackendPhase(false, "");
        if (progressEvent.lengthComputable && progressEvent.total > 0) {
          const rawPercent = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          const capped = Math.min(90, rawPercent);
          setProgress(capped, "Subiendo archivo...");
        } else {
          setProgress(10, "Subiendo archivo...");
        }
      });

      xhr.upload.addEventListener("loadend", function () {
        if (inFlight) {
          setProgress(90, "Archivo recibido. Iniciando procesamiento...");
          setBackendPhase(true, "Procesando historico en servidor...");
        }
      });

      xhr.addEventListener("load", function () {
        if (xhr.status >= 200 && xhr.status < 400) {
          let payload = null;
          try {
            payload = JSON.parse(xhr.responseText || "{}");
          } catch (e) {
            payload = null;
          }

          activeXhr = null;

          if (payload && payload.ok && payload.batch_progress_url) {
            currentBatchProgressUrl = payload.batch_progress_url;
            currentBatchCancelUrl = payload.batch_cancel_url || "";
            setProgress(91, "Procesamiento iniciado en servidor...");
            setBackendPhase(true, "Procesando historico en servidor...");
            pollBatchProgress(payload.redirect_url || action);
            return;
          }

          setProgress(100, "Carga completada. Redirigiendo...");
          setBackendPhase(true, "Proceso completado.");
          historicalCancel.disabled = true;
          window.location.href = xhr.responseURL || action;
          return;
        }

        const csrfMessage = xhr.status === 403 ? "La sesion de seguridad expiro (CSRF). Recarga la pagina e intenta de nuevo." : "No se pudo completar la importacion. Revisa el formulario.";
        setProgress(0, csrfMessage);
        setBackendPhase(false, "");
        resetInFlight();
      });

      xhr.addEventListener("error", function () {
        setProgress(0, "Error de red durante la carga. Intenta nuevamente.");
        setBackendPhase(false, "");
        resetInFlight();
      });

      xhr.addEventListener("abort", function () {
        setProgress(0, "La carga fue cancelada.");
        setBackendPhase(false, "");
        stopPolling();
        resetInFlight();
        closeModal();
      });

      xhr.send(formData);
    });
  }
});
