(() => {
    const cards = document.querySelectorAll(".sector-card");

    const showModal = (modal) => {
        if (!modal) return;
        modal.classList.remove("hidden");
        modal.classList.add("flex");
    };

    const hideModal = (modal) => {
        if (!modal) return;
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    };

    const setCardState = (card, expanded) => {
        const content = card.querySelector(".sector-content");
        const toggleBtn = card.querySelector(".sector-toggle-btn");
        if (!content || !toggleBtn) return;

        content.classList.toggle("hidden", !expanded);
        if (expanded) {
            toggleBtn.textContent = "Minimizar";
            toggleBtn.classList.remove("bg-emerald-500/20", "text-emerald-200", "border-emerald-400/40");
            toggleBtn.classList.add("bg-amber-500/20", "text-amber-200", "border-amber-400/40");
        } else {
            toggleBtn.textContent = "Maximizar";
            toggleBtn.classList.remove("bg-amber-500/20", "text-amber-200", "border-amber-400/40");
            toggleBtn.classList.add("bg-emerald-500/20", "text-emerald-200", "border-emerald-400/40");
        }
    };

    cards.forEach((card) => {
        const toggleBtn = card.querySelector(".sector-toggle-btn");
        const shouldOpen = card.getAttribute("data-open-default") === "1";
        setCardState(card, shouldOpen);

        toggleBtn?.addEventListener("click", () => {
            const isHidden = card.querySelector(".sector-content")?.classList.contains("hidden");
            setCardState(card, !!isHidden);
        });
    });

    const payload = JSON.parse(document.getElementById("sector-payload")?.textContent || "{}");
    const getSectorData = (sectorId) => payload[String(sectorId)] || { subsectors: [], categories: [] };

    const fillSelect = (select, items, getLabel, placeholder) => {
        if (!select) return;
        select.innerHTML = "";

        const firstOption = document.createElement("option");
        firstOption.value = "";
        firstOption.textContent = placeholder;
        select.appendChild(firstOption);

        items.forEach((item) => {
            const option = document.createElement("option");
            option.value = item.id;
            option.textContent = getLabel(item);
            select.appendChild(option);
        });
    };

    const sectorModal = document.getElementById("sector-modal");
    document.getElementById("open-sector-modal")?.addEventListener("click", () => showModal(sectorModal));
    document.getElementById("close-sector-modal")?.addEventListener("click", () => hideModal(sectorModal));
    sectorModal?.addEventListener("click", (event) => {
        if (event.target === sectorModal) hideModal(sectorModal);
    });

    const levelModal = document.getElementById("level-modal");
    const closeLevelModalBtn = document.getElementById("close-level-modal");
    const levelModalTitle = document.getElementById("level-modal-title");
    const levelModalSubtitle = document.getElementById("level-modal-subtitle");
    const levelSwitchButtons = document.querySelectorAll(".level-switch-btn");
    const levelForms = document.querySelectorAll(".level-form");
    const openLevelButtons = document.querySelectorAll(".open-level-modal");

    const activateLevelTab = (target) => {
        levelSwitchButtons.forEach((btn) => {
            const active = btn.getAttribute("data-level-target") === target;
            btn.classList.toggle("bg-sky-500/20", active);
            btn.classList.toggle("text-sky-200", active);
            btn.classList.toggle("border-sky-400/40", active);
            btn.classList.toggle("bg-slate-900/70", !active);
            btn.classList.toggle("text-slate-300", !active);
            btn.classList.toggle("border-white/10", !active);
        });

        levelForms.forEach((form) => {
            form.classList.toggle("hidden", form.getAttribute("data-level-form") !== target);
        });
    };

    const setModalSector = (sectorId, sectorName) => {
        if (!sectorId) return;

        if (levelModalTitle) levelModalTitle.textContent = `Crear nivel - ${sectorName}`;
        if (levelModalSubtitle) levelModalSubtitle.textContent = "Selecciona el nivel que deseas crear.";

        levelForms.forEach((form) => {
            const sectorInput = form.querySelector('input[name="sector_id"]');
            if (sectorInput) sectorInput.value = sectorId;
            const openSectorInput = form.querySelector('input[name="open_sector_id"]');
            if (openSectorInput) openSectorInput.value = sectorId;
        });

        const data = getSectorData(sectorId);
        const subsectorSelect = levelModal?.querySelector(".category-subsector-select");
        const categoryHelp = levelModal?.querySelector(".category-subsector-help");
        const categorySelect = levelModal?.querySelector(".entity-category-select");
        const entityHelp = levelModal?.querySelector(".entity-category-help");

        fillSelect(
            subsectorSelect,
            data.subsectors,
            (item) => `${item.name}${item.is_active ? "" : " (inactivo)"}`,
            "Selecciona subsector"
        );
        fillSelect(
            categorySelect,
            data.categories,
            (item) => `${item.subsector_name} / ${item.name}${item.is_active ? "" : " (inactiva)"}`,
            "Selecciona categoria"
        );

        const hasSubsectors = data.subsectors.length > 0;
        const hasCategories = data.categories.length > 0;

        if (subsectorSelect) subsectorSelect.disabled = !hasSubsectors;
        if (categoryHelp) categoryHelp.classList.toggle("hidden", hasSubsectors);
        if (categorySelect) categorySelect.disabled = !hasCategories;
        if (entityHelp) entityHelp.classList.toggle("hidden", hasCategories);
    };

    openLevelButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const sectorId = button.getAttribute("data-sector-id");
            const sectorName = button.getAttribute("data-sector-name") || "Sector";
            setModalSector(sectorId, sectorName);
            activateLevelTab("subsector");
            showModal(levelModal);
        });
    });

    levelSwitchButtons.forEach((button) => {
        button.addEventListener("click", () => activateLevelTab(button.getAttribute("data-level-target")));
    });

    closeLevelModalBtn?.addEventListener("click", () => hideModal(levelModal));
    levelModal?.addEventListener("click", (event) => {
        if (event.target === levelModal) hideModal(levelModal);
    });

    const sectorEditModal = document.getElementById("sector-edit-modal");
    const sectorEditForm = document.getElementById("sector-edit-form");

    document.querySelectorAll("[data-open-edit-sector]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!sectorEditForm) return;

            const sectorId = button.getAttribute("data-sector-id") || "";
            const sectorName = button.getAttribute("data-sector-name") || "";
            const sectorDescription = button.getAttribute("data-sector-description") || "";

            const sectorIdInput = sectorEditForm.querySelector('input[name="sector_id"]');
            const openSectorIdInput = sectorEditForm.querySelector('input[name="open_sector_id"]');
            const nameInput = sectorEditForm.querySelector('input[name="sector_name"]');
            const descriptionInput = sectorEditForm.querySelector('textarea[name="sector_description"]');

            if (sectorIdInput) sectorIdInput.value = sectorId;
            if (openSectorIdInput) openSectorIdInput.value = sectorId;
            if (nameInput) nameInput.value = sectorName;
            if (descriptionInput) descriptionInput.value = sectorDescription;

            showModal(sectorEditModal);
        });
    });

    document.getElementById("close-sector-edit-modal")?.addEventListener("click", () => hideModal(sectorEditModal));
    sectorEditModal?.addEventListener("click", (event) => {
        if (event.target === sectorEditModal) hideModal(sectorEditModal);
    });

    const sectorDeleteModal = document.getElementById("sector-delete-modal");
    const sectorDeleteForm = document.getElementById("sector-delete-form");
    const sectorDeleteMessage = document.getElementById("sector-delete-message");

    document.querySelectorAll("[data-open-delete-sector]").forEach((button) => {
        button.addEventListener("click", () => {
            if (button.hasAttribute("disabled") || !sectorDeleteForm) return;

            const sectorId = button.getAttribute("data-sector-id") || "";
            const sectorName = button.getAttribute("data-sector-name") || "";
            const impactSummary = button.getAttribute("data-impact-summary") || "";

            const sectorIdInput = sectorDeleteForm.querySelector('input[name="sector_id"]');
            if (sectorIdInput) sectorIdInput.value = sectorId;

            if (sectorDeleteMessage) {
                let message = `Estas por eliminar el sector "${sectorName}". Esta accion no se puede deshacer.`;
                if (impactSummary) {
                    message += ` Impacto detectado: ${impactSummary}.`;
                }
                sectorDeleteMessage.textContent = message;
            }

            showModal(sectorDeleteModal);
        });
    });

    document.getElementById("close-sector-delete-modal")?.addEventListener("click", () => hideModal(sectorDeleteModal));
    document.getElementById("cancel-sector-delete")?.addEventListener("click", () => hideModal(sectorDeleteModal));
    sectorDeleteModal?.addEventListener("click", (event) => {
        if (event.target === sectorDeleteModal) hideModal(sectorDeleteModal);
    });

    const subsectorEditModal = document.getElementById("subsector-edit-modal");
    const subsectorEditForm = document.getElementById("subsector-edit-form");

    document.querySelectorAll("[data-open-edit-subsector]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!subsectorEditForm) return;

            const openSectorId = button.getAttribute("data-open-sector-id") || "";
            const subsectorId = button.getAttribute("data-subsector-id") || "";
            const name = button.getAttribute("data-subsector-name") || "";
            const description = button.getAttribute("data-subsector-description") || "";

            const subsectorIdInput = subsectorEditForm.querySelector('input[name="subsector_id"]');
            const openSectorIdInput = subsectorEditForm.querySelector('input[name="open_sector_id"]');
            const nameInput = subsectorEditForm.querySelector('input[name="subsector_name"]');
            const descriptionInput = subsectorEditForm.querySelector('textarea[name="subsector_description"]');

            if (subsectorIdInput) subsectorIdInput.value = subsectorId;
            if (openSectorIdInput) openSectorIdInput.value = openSectorId;
            if (nameInput) nameInput.value = name;
            if (descriptionInput) descriptionInput.value = description;

            showModal(subsectorEditModal);
        });
    });

    document.getElementById("close-subsector-edit-modal")?.addEventListener("click", () => hideModal(subsectorEditModal));
    subsectorEditModal?.addEventListener("click", (event) => {
        if (event.target === subsectorEditModal) hideModal(subsectorEditModal);
    });

    const categoryEditModal = document.getElementById("category-edit-modal");
    const categoryEditForm = document.getElementById("category-edit-form");
    const categoryEditPath = document.getElementById("category-edit-path");

    document.querySelectorAll("[data-open-edit-category]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!categoryEditForm) return;

            const openSectorId = button.getAttribute("data-open-sector-id") || "";
            const categoryId = button.getAttribute("data-category-id") || "";
            const name = button.getAttribute("data-category-name") || "";
            const description = button.getAttribute("data-category-description") || "";
            const path = button.getAttribute("data-category-path") || "";

            const categoryIdInput = categoryEditForm.querySelector('input[name="category_id"]');
            const openSectorIdInput = categoryEditForm.querySelector('input[name="open_sector_id"]');
            const nameInput = categoryEditForm.querySelector('input[name="category_name"]');
            const descriptionInput = categoryEditForm.querySelector('textarea[name="category_description"]');

            if (categoryIdInput) categoryIdInput.value = categoryId;
            if (openSectorIdInput) openSectorIdInput.value = openSectorId;
            if (nameInput) nameInput.value = name;
            if (descriptionInput) descriptionInput.value = description;
            if (categoryEditPath) {
                categoryEditPath.textContent = path ? `Categoria: ${path}` : "Actualiza nombre y descripcion.";
            }

            showModal(categoryEditModal);
        });
    });

    document.getElementById("close-category-edit-modal")?.addEventListener("click", () => hideModal(categoryEditModal));
    categoryEditModal?.addEventListener("click", (event) => {
        if (event.target === categoryEditModal) hideModal(categoryEditModal);
    });

    const entityEditModal = document.getElementById("entity-edit-modal");
    const entityEditForm = document.getElementById("entity-edit-form");

    const fillEntityEditCategories = (sectorId, selectedCategoryId) => {
        if (!entityEditForm) return;

        const categorySelect = entityEditForm.querySelector('select[name="category_id"]');
        const help = entityEditForm.querySelector(".entity-edit-category-help");
        const categories = getSectorData(sectorId).categories;

        fillSelect(
            categorySelect,
            categories,
            (item) => `${item.subsector_name} / ${item.name}${item.is_active ? "" : " (inactiva)"}`,
            "Selecciona categoria"
        );

        const hasCategories = categories.length > 0;
        if (categorySelect) {
            categorySelect.disabled = !hasCategories;
            if (selectedCategoryId) {
                categorySelect.value = String(selectedCategoryId);
            }
        }
        if (help) {
            help.classList.toggle("hidden", hasCategories);
        }
    };

    document.querySelectorAll("[data-open-edit-entity]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!entityEditForm) return;

            const openSectorId = button.getAttribute("data-open-sector-id") || "";
            const sectorId = button.getAttribute("data-sector-id") || openSectorId;
            const entityId = button.getAttribute("data-entity-id") || "";
            const categoryId = button.getAttribute("data-category-id") || "";
            const name = button.getAttribute("data-entity-name") || "";
            const code = button.getAttribute("data-entity-code") || "";
            const description = button.getAttribute("data-entity-description") || "";

            const entityIdInput = entityEditForm.querySelector('input[name="entity_id"]');
            const openSectorIdInput = entityEditForm.querySelector('input[name="open_sector_id"]');
            const nameInput = entityEditForm.querySelector('input[name="entity_name"]');
            const codeInput = entityEditForm.querySelector('input[name="entity_code"]');
            const descriptionInput = entityEditForm.querySelector('textarea[name="entity_description"]');

            if (entityIdInput) entityIdInput.value = entityId;
            if (openSectorIdInput) openSectorIdInput.value = openSectorId;
            if (nameInput) nameInput.value = name;
            if (codeInput) codeInput.value = code;
            if (descriptionInput) descriptionInput.value = description;

            fillEntityEditCategories(sectorId, categoryId);
            showModal(entityEditModal);
        });
    });

    document.getElementById("close-entity-edit-modal")?.addEventListener("click", () => hideModal(entityEditModal));
    entityEditModal?.addEventListener("click", (event) => {
        if (event.target === entityEditModal) hideModal(entityEditModal);
    });

    const levelDeleteModal = document.getElementById("level-delete-modal");
    const levelDeleteForm = document.getElementById("level-delete-form");
    const levelDeleteTitle = document.getElementById("level-delete-title");
    const levelDeleteMessage = document.getElementById("level-delete-message");

    document.querySelectorAll("[data-open-delete-level]").forEach((button) => {
        button.addEventListener("click", () => {
            if (button.hasAttribute("disabled") || !levelDeleteForm) return;

            const levelLabel = button.getAttribute("data-level-label") || "nivel";
            const itemName = button.getAttribute("data-item-name") || "";
            const deleteAction = button.getAttribute("data-delete-action") || "";
            const targetField = button.getAttribute("data-target-field") || "";
            const targetId = button.getAttribute("data-target-id") || "";
            const openSectorId = button.getAttribute("data-open-sector-id") || "";
            const impactSummary = button.getAttribute("data-impact-summary") || "";

            const actionInput = levelDeleteForm.querySelector('input[name="action"]');
            const openSectorInput = levelDeleteForm.querySelector('input[name="open_sector_id"]');
            const subsectorInput = levelDeleteForm.querySelector('input[name="subsector_id"]');
            const categoryInput = levelDeleteForm.querySelector('input[name="category_id"]');
            const entityInput = levelDeleteForm.querySelector('input[name="entity_id"]');

            if (actionInput) actionInput.value = deleteAction;
            if (openSectorInput) openSectorInput.value = openSectorId;
            if (subsectorInput) subsectorInput.value = "";
            if (categoryInput) categoryInput.value = "";
            if (entityInput) entityInput.value = "";

            const targetInput = levelDeleteForm.querySelector(`input[name="${targetField}"]`);
            if (targetInput) targetInput.value = targetId;

            if (levelDeleteTitle) {
                levelDeleteTitle.textContent = `Eliminar ${levelLabel}`;
            }

            if (levelDeleteMessage) {
                let message = `Estas por eliminar ${levelLabel} "${itemName}". Esta accion no se puede deshacer.`;
                if (impactSummary) {
                    message += ` Impacto detectado: ${impactSummary}.`;
                }
                levelDeleteMessage.textContent = message;
            }

            showModal(levelDeleteModal);
        });
    });

    document.getElementById("close-level-delete-modal")?.addEventListener("click", () => hideModal(levelDeleteModal));
    document.getElementById("cancel-level-delete")?.addEventListener("click", () => hideModal(levelDeleteModal));
    levelDeleteModal?.addEventListener("click", (event) => {
        if (event.target === levelDeleteModal) hideModal(levelDeleteModal);
    });

    activateLevelTab("subsector");
})();
