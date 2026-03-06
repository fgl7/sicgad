document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("[data-formula-approve-form]");
  const modal = document.getElementById("formula-approve-modal");
  const percentEl = document.getElementById("formula-approve-percent");
  const progressEl = document.getElementById("formula-approve-progress");
  const statusTextEl = document.getElementById("formula-approve-status-text");
  const detailTextEl = document.getElementById("formula-approve-detail-text");
  const stageEl = document.getElementById("formula-approve-stage");
  if (!form || !modal || !percentEl || !progressEl) {
    return;
  }

  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }

  const submitBtn = form.querySelector("[data-formula-approve-btn]");
  let submitting = false;
  let pollTimer = null;
  let progressUrl = "";

  function setProgress(value) {
    const v = Math.max(0, Math.min(100, Number(value) || 0));
    percentEl.textContent = `${Math.round(v)}%`;
    progressEl.style.width = `${v}%`;
  }

  function setStage(payload) {
    if (!stageEl) return;
    const idx = Number(payload && payload.stage_index);
    const total = Number(payload && payload.stage_total);
    const label = payload && payload.stage_label ? String(payload.stage_label) : "";
    const status = payload && payload.status ? String(payload.status).toUpperCase() : "";
    stageEl.className = "px-2 py-0.5 rounded-md text-[10px] font-semibold";
    if (!idx || !total) {
      stageEl.classList.add("hidden");
      stageEl.textContent = "";
      return;
    }
    if (status === "FAILED") {
      stageEl.classList.add("border", "border-red-400/30", "bg-red-400/10", "text-red-100");
    } else if (status === "DONE") {
      stageEl.classList.add("border", "border-emerald-400/30", "bg-emerald-400/10", "text-emerald-100");
    } else if (idx >= 3) {
      stageEl.classList.add("border", "border-cyan-400/30", "bg-cyan-400/10", "text-cyan-100");
    } else {
      stageEl.classList.add("border", "border-sky-400/30", "bg-sky-400/10", "text-sky-100");
    }
    stageEl.textContent = `Etapa ${idx}/${total}${label ? " - " + label : ""}`;
    stageEl.classList.remove("hidden");
  }

  function stopPolling() {
    if (pollTimer) {
      window.clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function pollProgress() {
    if (!submitting || !progressUrl) return;
    fetch(progressUrl, {
      credentials: "same-origin",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json"
      }
    })
      .then((response) => {
        if (!response.ok) throw new Error("No se pudo consultar el progreso.");
        return response.json();
      })
      .then((payload) => {
        if (payload && typeof payload.percent === "number") setProgress(payload.percent);
        if (payload && payload.message && detailTextEl) detailTextEl.textContent = payload.message;
        setStage(payload || {});
        if (payload && (payload.status === "DONE" || payload.status === "FAILED")) {
          stopPolling();
          return;
        }
        pollTimer = window.setTimeout(pollProgress, 700);
      })
      .catch(() => {
        if (!submitting) return;
        pollTimer = window.setTimeout(pollProgress, 1200);
      });
  }

  function resetUi() {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove("opacity-70", "cursor-not-allowed");
      submitBtn.textContent = "Aprobar formula";
    }
    submitting = false;
  }

  form.addEventListener("submit", function (event) {
    if (submitting) {
      event.preventDefault();
      return;
    }
    event.preventDefault();
    submitting = true;
    progressUrl = form.getAttribute("data-formula-approve-progress-url") || "";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.classList.add("opacity-70", "cursor-not-allowed");
      submitBtn.textContent = "Procesando...";
    }
    if (statusTextEl) statusTextEl.textContent = "Aprobando formula...";
    if (detailTextEl) detailTextEl.textContent = "Preparando aprobacion y materializacion...";
    setProgress(1);
    setStage({ stage_index: 1, stage_total: 4, stage_label: "Preparacion", status: "RUNNING" });
    modal.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
    stopPolling();
    if (progressUrl) pollProgress();

    const submitUrl = form.getAttribute("action") || window.location.href;
    fetch(submitUrl, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json"
      }
    })
      .then((response) => {
        if (!response.ok) throw new Error("No se pudo aprobar la formula.");
        const contentType = response.headers.get("content-type") || "";
        if (contentType.indexOf("application/json") === -1) {
          return { ok: true, redirect_url: window.location.href, message: "Aprobacion procesada." };
        }
        return response.json();
      })
      .then((payload) => {
        stopPolling();
        setProgress(100);
        setStage(payload || { stage_index: 4, stage_total: 4, stage_label: "Completado", status: "DONE" });
        if (statusTextEl) statusTextEl.textContent = "Aprobacion completada. Redirigiendo...";
        if (detailTextEl) detailTextEl.textContent = (payload && payload.message) ? payload.message : "Proceso completado.";
        const redirectUrl = (payload && payload.redirect_url) ? payload.redirect_url : window.location.href;
        window.setTimeout(function () {
          window.location.href = redirectUrl;
        }, 180);
      })
      .catch((error) => {
        console.error(error);
        stopPolling();
        setProgress(100);
        setStage({ stage_index: 4, stage_total: 4, stage_label: "Error", status: "FAILED" });
        if (statusTextEl) statusTextEl.textContent = "No se pudo aprobar la formula.";
        if (detailTextEl) detailTextEl.textContent = "Intenta nuevamente desde el builder.";
        resetUi();
        window.setTimeout(function () {
          modal.classList.add("hidden");
          document.body.classList.remove("overflow-hidden");
        }, 800);
      });
  });

  const deleteForms = document.querySelectorAll("[data-formula-delete-form]");
  const deleteModal = document.getElementById("formula-delete-modal");
  const nameEl = document.getElementById("formula-delete-name");
  const confirmBtn = document.getElementById("formula-delete-confirm-btn");
  const cancelEls = document.querySelectorAll("[data-formula-delete-cancel]");
  const approveModal = document.getElementById("formula-approve-modal");
  if (!deleteForms.length || !deleteModal || !nameEl || !confirmBtn) {
    return;
  }

  if (deleteModal.parentElement !== document.body) {
    document.body.appendChild(deleteModal);
  }

  let activeDeleteForm = null;

  function unlockBodyIfNoOtherModal() {
    const approveVisible = !!(approveModal && !approveModal.classList.contains("hidden"));
    if (!approveVisible) {
      document.body.classList.remove("overflow-hidden");
    }
  }

  function closeDeleteModal() {
    deleteModal.classList.add("hidden");
    activeDeleteForm = null;
    unlockBodyIfNoOtherModal();
  }

  function openDeleteModal(formEl) {
    activeDeleteForm = formEl;
    const label = (formEl.getAttribute("data-formula-label") || "").trim();
    nameEl.textContent = label ? `"${label}"` : "seleccionada";
    deleteModal.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
  }

  deleteForms.forEach(function (formEl) {
    formEl.addEventListener("submit", function (event) {
      event.preventDefault();
      openDeleteModal(formEl);
    });
  });

  cancelEls.forEach(function (el) {
    el.addEventListener("click", function () {
      closeDeleteModal();
    });
  });

  confirmBtn.addEventListener("click", function () {
    if (!activeDeleteForm) {
      closeDeleteModal();
      return;
    }
    const formToSubmit = activeDeleteForm;
    activeDeleteForm = null;
    confirmBtn.disabled = true;
    confirmBtn.classList.add("opacity-70", "cursor-not-allowed");
    formToSubmit.submit();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !deleteModal.classList.contains("hidden")) {
      closeDeleteModal();
    }
  });
});
