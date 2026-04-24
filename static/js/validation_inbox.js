document.addEventListener("DOMContentLoaded", function () {
  const approveForms = document.querySelectorAll("[data-historical-approve-form]");
  const modal = document.getElementById("historical-approve-modal");
  const percentEl = document.getElementById("historical-approve-percent");
  const progressEl = document.getElementById("historical-approve-progress");
  const statusTextEl = document.getElementById("historical-approve-status-text");
  const detailTextEl = document.getElementById("historical-approve-detail-text");
  const stageEl = document.getElementById("historical-approve-stage");

  if (!approveForms.length || !modal || !percentEl || !progressEl) {
    return;
  }

  let submitting = false;
  let progressValue = 0;
  let progressTimer = null;
  let progressPollTimer = null;
  let activeButton = null;
  let activeProgressUrl = "";
  let activeApproveRequest = null;
  const stageToneClasses = [
    "border", "border-sky-400/30", "bg-sky-400/10", "text-sky-100",
    "border-cyan-400/30", "bg-cyan-400/10", "text-cyan-100",
    "border-amber-400/30", "bg-amber-400/10", "text-amber-100",
    "border-emerald-400/30", "bg-emerald-400/10", "text-emerald-100",
    "border-red-400/30", "bg-red-400/10", "text-red-100"
  ];

  function setProgress(value) {
    const clamped = Math.max(0, Math.min(100, value));
    progressValue = clamped;
    percentEl.textContent = `${clamped}%`;
    progressEl.style.width = `${clamped}%`;
  }

  function startProgressSimulation() {
    setProgress(0);
    if (progressTimer) {
      clearInterval(progressTimer);
    }
    progressTimer = setInterval(function () {
      if (progressValue >= 95) {
        clearInterval(progressTimer);
        progressTimer = null;
        return;
      }
      const step = progressValue < 60 ? 5 : (progressValue < 85 ? 2 : 1);
      setProgress(progressValue + step);
    }, 250);
  }

  function setStage(payload) {
    if (!stageEl) {
      return;
    }
    const idx = payload && Number.isFinite(Number(payload.stage_index)) ? Number(payload.stage_index) : null;
    const total = payload && Number.isFinite(Number(payload.stage_total)) ? Number(payload.stage_total) : null;
    const label = payload && payload.stage_label ? String(payload.stage_label) : "";
    const status = payload && payload.status ? String(payload.status).toUpperCase() : "";
    if (!idx || !total) {
      stageEl.textContent = "";
      stageEl.classList.remove(...stageToneClasses);
      stageEl.classList.add("hidden");
      return;
    }
    stageEl.classList.remove(...stageToneClasses);
    if (status === "FAILED") {
      stageEl.classList.add("border", "border-red-400/30", "bg-red-400/10", "text-red-100");
    } else if (status === "DONE" || idx >= 4) {
      stageEl.classList.add("border", "border-emerald-400/30", "bg-emerald-400/10", "text-emerald-100");
    } else if (idx === 3) {
      stageEl.classList.add("border", "border-amber-400/30", "bg-amber-400/10", "text-amber-100");
    } else if (idx === 2) {
      stageEl.classList.add("border", "border-cyan-400/30", "bg-cyan-400/10", "text-cyan-100");
    } else {
      stageEl.classList.add("border", "border-sky-400/30", "bg-sky-400/10", "text-sky-100");
    }
    stageEl.textContent = `Etapa ${idx}/${total}${label ? " - " + label : ""}`;
    stageEl.classList.remove("hidden");
  }

  function stopProgressSimulation() {
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }
  }

  function stopProgressPolling() {
    if (progressPollTimer) {
      clearTimeout(progressPollTimer);
      progressPollTimer = null;
    }
  }

  function pollApprovalProgress() {
    if (!submitting || !activeProgressUrl) {
      return;
    }

    fetch(activeProgressUrl, {
      credentials: "same-origin",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json"
      }
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("No se pudo consultar el progreso.");
        }
        return response.json();
      })
      .then(function (payload) {
        if (!payload || payload.ok === false) {
          throw new Error((payload && payload.error) || "Sin datos de progreso.");
        }

        if (typeof payload.percent === "number") {
          setProgress(payload.percent);
        }
        setStage(payload);
        if (statusTextEl && payload.message) {
          statusTextEl.textContent = "Aprobando lote histórico...";
        }
        if (detailTextEl && payload.message) {
          detailTextEl.textContent = payload.message;
        }

        if (payload.status === "DONE" || payload.status === "FAILED") {
          stopProgressPolling();
          return;
        }

        progressPollTimer = window.setTimeout(pollApprovalProgress, 700);
      })
      .catch(function () {
        if (!submitting) {
          return;
        }
        progressPollTimer = window.setTimeout(pollApprovalProgress, 1200);
      });
  }

  function resetUiAfterError(message) {
    stopProgressSimulation();
    stopProgressPolling();
    if (statusTextEl) {
      statusTextEl.textContent = message || "No se pudo aprobar el lote histórico.";
    }
    if (detailTextEl) {
      detailTextEl.textContent = "Puedes intentar nuevamente desde la bandeja.";
    }
    setStage({ status: "FAILED", stage_index: 4, stage_total: 4, stage_label: "Error" });
    if (activeButton) {
      activeButton.disabled = false;
      activeButton.classList.remove("opacity-70", "cursor-not-allowed");
      activeButton.textContent = "Aprobar lote";
    }
    submitting = false;
  }

  approveForms.forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (submitting) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      submitting = true;

      const button = form.querySelector("[data-historical-approve-btn]");
      activeButton = button || null;
      if (button) {
        button.disabled = true;
        button.classList.add("opacity-70", "cursor-not-allowed");
        button.textContent = "Procesando...";
      }

      if (statusTextEl) {
        statusTextEl.textContent = "Aprobando lote histórico...";
      }
      if (detailTextEl) {
        detailTextEl.textContent = "Preparando aprobación del histórico...";
      }
      setStage({ stage_index: 1, stage_total: 4, stage_label: "Preparación" });
      modal.classList.remove("hidden");
      document.body.classList.add("overflow-hidden");
      stopProgressPolling();
      activeProgressUrl = form.getAttribute("data-historical-approve-progress-url") || "";
      setProgress(1);
      if (activeProgressUrl) {
        pollApprovalProgress();
      } else {
        startProgressSimulation();
      }

      activeApproveRequest = fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "Accept": "application/json"
        }
      })
        .then(function (response) {
          activeApproveRequest = null;
          if (!response.ok) {
            throw new Error("Error al aprobar el lote histórico.");
          }
          const contentType = response.headers.get("content-type") || "";
          if (contentType.indexOf("application/json") === -1) {
            return { ok: true, redirect_url: window.location.href };
          }
          return response.json();
        })
        .then(function (payload) {
          stopProgressSimulation();
          stopProgressPolling();
          setProgress(100);
          if (statusTextEl) {
            statusTextEl.textContent = "Aprobación completada. Redirigiendo...";
          }
          setStage(payload || { stage_index: 4, stage_total: 4, stage_label: "Completado" });
          if (detailTextEl) {
            detailTextEl.textContent = (payload && payload.message) ? payload.message : "Proceso completado.";
          }
          const redirectUrl = (payload && payload.redirect_url) ? payload.redirect_url : window.location.href;
          window.setTimeout(function () {
            window.location.href = redirectUrl;
          }, 180);
        })
        .catch(function (error) {
          activeApproveRequest = null;
          console.error(error);
          resetUiAfterError("No se pudo aprobar el lote histórico. Intente nuevamente.");
          window.setTimeout(function () {
            activeProgressUrl = "";
            setStage(null);
            modal.classList.add("hidden");
            document.body.classList.remove("overflow-hidden");
          }, 700);
        });
    });
  });
});
