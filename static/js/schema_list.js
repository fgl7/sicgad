document.addEventListener("DOMContentLoaded", function () {
  const modal = document.getElementById("schema-reject-modal");
  const form = document.getElementById("schema-reject-form");
  const commentField = document.getElementById("schema-reject-comment");
  const datasetLabel = document.getElementById("schema-reject-modal-dataset");

  if (!modal || !form || !commentField || !datasetLabel) {
    return;
  }

  function openModal(rejectUrl, datasetName, datasetPlant) {
    form.action = rejectUrl || "";
    commentField.value = "";
    datasetLabel.textContent = datasetName
      ? `Estás rechazando el esquema "${datasetName}" de la planta ${datasetPlant}.`
      : "Estás rechazando este esquema.";

    modal.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
    commentField.focus();
  }

  function closeModal() {
    modal.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  document.body.addEventListener("click", function (event) {
    const openBtn = event.target.closest("[data-open-reject-modal]");
    if (openBtn) {
      const rejectUrl = openBtn.getAttribute("data-reject-url");
      const datasetName = openBtn.getAttribute("data-dataset-name") || "";
      const datasetPlant = openBtn.getAttribute("data-dataset-plant") || "";
      openModal(rejectUrl, datasetName, datasetPlant);
      return;
    }

    if (event.target.closest("[data-close-reject-modal]")) {
      closeModal();
      return;
    }
  });

  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      closeModal();
    }
  });
});

