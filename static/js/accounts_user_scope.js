(() => {
    const scopeSelect = document.getElementById("id_scope_mode");
    const sectorSelect = document.getElementById("id_sector");
    const subsectorSelect = document.getElementById("id_subsector");
    const categorySelect = document.getElementById("id_category");
    const entitySelect = document.getElementById("id_entity");
    const entityContainer = document.querySelector("[data-entity-container]");
    const roleSelect = document.getElementById("id_role");
    const viewerProfileContainer = document.querySelector("[data-viewer-profile-container]");
    const validationPermissionsSection = document.querySelector("[data-validation-permissions-section]");
    const viewerProfileSelect = document.getElementById("id_viewer_profile_type");
    const standardScopeContainers = document.querySelectorAll("[data-standard-scope-container]");
    const authorityScopeContainer = document.querySelector("[data-authority-scope-container]");
    const authorityScopeSelect = document.getElementById("id_authority_scope_mode");
    const authoritySectorContainer = document.querySelector("[data-authority-sector-container]");
    const authoritySectorSelect = document.getElementById("id_authority_sector");

    if (!scopeSelect || !entitySelect || !entityContainer) {
        return;
    }

    function createMultiSelectUI(select, placeholder) {
        if (!select || !select.multiple) {
            return null;
        }

        const shell = document.createElement("div");
        shell.className = "multi-select-shell";

        const chips = document.createElement("div");
        chips.className = "multi-select-chips";

        const search = document.createElement("input");
        search.type = "text";
        search.className = "multi-select-search";
        search.placeholder = placeholder;

        const options = document.createElement("div");
        options.className = "multi-select-options custom-scrollbar";

        select.classList.add("hidden");
        select.parentNode.insertBefore(shell, select.nextSibling);
        shell.appendChild(chips);
        shell.appendChild(search);
        shell.appendChild(options);

        const state = {
            term: "",
            disabled: select.disabled,
        };

        const syncSelectedFromUI = (value, selected) => {
            const target = Array.from(select.options).find((opt) => opt.value === value);
            if (target) {
                target.selected = selected;
            }
        };

        const renderChips = () => {
            chips.innerHTML = "";
            const selected = Array.from(select.selectedOptions).filter((opt) => opt.value);
            if (!selected.length) {
                const empty = document.createElement("span");
                empty.className = "multi-select-empty";
                empty.textContent = "Sin seleccion";
                chips.appendChild(empty);
                return;
            }

            selected.forEach((opt) => {
                const chip = document.createElement("span");
                chip.className = "multi-chip";
                chip.textContent = opt.textContent.trim();

                const removeBtn = document.createElement("button");
                removeBtn.type = "button";
                removeBtn.className = "multi-chip-remove";
                removeBtn.textContent = "x";
                removeBtn.disabled = state.disabled;
                removeBtn.addEventListener("click", () => {
                    syncSelectedFromUI(opt.value, false);
                    render();
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                });

                chip.appendChild(removeBtn);
                chips.appendChild(chip);
            });
        };

        const renderOptions = () => {
            options.innerHTML = "";
            const term = state.term.toLowerCase();
            const all = Array.from(select.options).filter((opt) => opt.value);
            const visible = all.filter((opt) => {
                if (opt.hidden || opt.disabled) {
                    return false;
                }
                if (!term) {
                    return true;
                }
                return opt.textContent.toLowerCase().includes(term);
            });

            if (!visible.length) {
                const empty = document.createElement("div");
                empty.className = "multi-select-no-results";
                empty.textContent = "Sin resultados";
                options.appendChild(empty);
                return;
            }

            visible.forEach((opt) => {
                const row = document.createElement("button");
                row.type = "button";
                row.className = `multi-option ${opt.selected ? "active" : ""}`;
                row.disabled = state.disabled;
                row.textContent = opt.textContent.trim();
                row.addEventListener("click", () => {
                    syncSelectedFromUI(opt.value, !opt.selected);
                    render();
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                });
                options.appendChild(row);
            });
        };

        const render = () => {
            shell.classList.toggle("is-disabled", state.disabled);
            search.disabled = state.disabled;
            renderChips();
            renderOptions();
        };

        search.addEventListener("input", () => {
            state.term = search.value || "";
            renderOptions();
        });

        return {
            refresh: render,
            clear: () => {
                Array.from(select.options).forEach((opt) => {
                    opt.selected = false;
                });
                render();
            },
            setDisabled: (disabled) => {
                state.disabled = disabled;
                render();
            },
        };
    }

    const sectorUI = createMultiSelectUI(sectorSelect, "Buscar sectores...");
    const subsectorUI = createMultiSelectUI(subsectorSelect, "Buscar subsectores...");
    const categoryUI = createMultiSelectUI(categorySelect, "Buscar categorias...");
    const entityUI = createMultiSelectUI(entitySelect, "Buscar entidades...");

    const getSelectedValues = (select) => {
        if (!select) {
            return [];
        }
        return Array.from(select.selectedOptions || [])
            .filter((opt) => opt.value)
            .map((opt) => opt.value);
    };

    const clearMultiSelection = (select, ui) => {
        if (!select) {
            return;
        }
        Array.from(select.options || []).forEach((option) => {
            option.selected = false;
        });
        if (ui) {
            ui.refresh();
        }
    };

    const filterSubsectorsBySector = () => {
        if (!subsectorSelect) {
            return;
        }
        const selectedSectorIds = getSelectedValues(sectorSelect);
        Array.from(subsectorSelect.options || []).forEach((option) => {
            if (!option.value) {
                return;
            }
            const optionSector = option.dataset.sectorId || "";
            const matches = selectedSectorIds.length === 0 || selectedSectorIds.includes(optionSector);
            option.hidden = !matches;
            option.disabled = !matches;
            if (!matches && option.selected) {
                option.selected = false;
            }
        });
        if (subsectorUI) {
            subsectorUI.refresh();
        }
    };

    const filterCategoriesBySubsector = () => {
        if (!categorySelect) {
            return;
        }
        const selectedSectorIds = getSelectedValues(sectorSelect);
        const selectedSubsectorIds = getSelectedValues(subsectorSelect);
        Array.from(categorySelect.options || []).forEach((option) => {
            if (!option.value) {
                return;
            }
            const optionSubsector = option.dataset.subsectorId || "";
            const optionSector = option.dataset.sectorId || "";
            const matchesSector = selectedSectorIds.length === 0 || selectedSectorIds.includes(optionSector);
            const matchesSubsector =
                selectedSubsectorIds.length === 0 || selectedSubsectorIds.includes(optionSubsector);
            const visible = matchesSector && matchesSubsector;
            option.hidden = !visible;
            option.disabled = !visible;
            if (!visible && option.selected) {
                option.selected = false;
            }
        });
        if (categoryUI) {
            categoryUI.refresh();
        }
    };

    const filterEntitiesByCategories = () => {
        if (!entitySelect) {
            return;
        }
        const selectedSectorIds = getSelectedValues(sectorSelect);
        const selectedSubsectorIds = getSelectedValues(subsectorSelect);
        const selectedCategoryIds = getSelectedValues(categorySelect);

        Array.from(entitySelect.options || []).forEach((option) => {
            if (!option.value) {
                return;
            }
            const optionCategory = option.dataset.categoryId || "";
            const optionSubsector = option.dataset.subsectorId || "";
            const optionSector = option.dataset.sectorId || "";
            const matchesSector = selectedSectorIds.length === 0 || selectedSectorIds.includes(optionSector);
            const matchesSubsector =
                selectedSubsectorIds.length === 0 || selectedSubsectorIds.includes(optionSubsector);
            const matchesCategory =
                selectedCategoryIds.length > 0 && selectedCategoryIds.includes(optionCategory);
            const visible = matchesSector && matchesSubsector && matchesCategory;
            option.hidden = !visible;
            option.disabled = !visible;
            if (!visible && option.selected) {
                option.selected = false;
            }
        });
        if (entityUI) {
            entityUI.refresh();
        }
    };

    const toggleEntityField = () => {
        const isGlobalCategory = scopeSelect.value === "CATEGORY_GLOBAL";
        entityContainer.classList.toggle("opacity-50", isGlobalCategory);
        entityContainer.classList.toggle("pointer-events-none", isGlobalCategory);
        if (isGlobalCategory) {
            clearMultiSelection(entitySelect, entityUI);
        }
    };

    const toggleViewerProfileField = () => {
        if (!roleSelect || !viewerProfileContainer) {
            return;
        }
        const isViewer = roleSelect.value === "VIEWER";
        viewerProfileContainer.classList.toggle("opacity-50", !isViewer);
        viewerProfileContainer.classList.toggle("pointer-events-none", !isViewer);

        const field = viewerProfileContainer.querySelector("select");
        if (field) {
            field.disabled = !isViewer;
            if (!isViewer) {
                field.value = "STANDARD";
            }
        }
    };

    const toggleValidationPermissionsSection = () => {
        if (!roleSelect || !validationPermissionsSection) {
            return;
        }
        const isViewer = roleSelect.value === "VIEWER";
        validationPermissionsSection.classList.toggle("hidden", isViewer);
    };

    const toggleScopeByViewerType = () => {
        standardScopeContainers.forEach((container) => {
            container.classList.remove("hidden");
        });
        if (authorityScopeContainer) {
            authorityScopeContainer.classList.add("hidden");
        }

        if (scopeSelect) {
            scopeSelect.disabled = false;
        }
        if (sectorSelect) {
            sectorSelect.disabled = false;
            if (sectorUI) {
                sectorUI.setDisabled(false);
            }
        }
        if (subsectorSelect) {
            subsectorSelect.disabled = false;
            if (subsectorUI) {
                subsectorUI.setDisabled(false);
            }
        }
        if (categorySelect) {
            categorySelect.disabled = false;
            if (categoryUI) {
                categoryUI.setDisabled(false);
            }
        }
        if (entitySelect) {
            const disabled = entityContainer.classList.contains("pointer-events-none");
            entitySelect.disabled = disabled;
            if (entityUI) {
                entityUI.setDisabled(disabled);
            }
        }

        if (authorityScopeSelect) {
            authorityScopeSelect.disabled = true;
            authorityScopeSelect.value = "SECTOR";
        }
        if (authoritySectorSelect) {
            authoritySectorSelect.disabled = true;
            authoritySectorSelect.value = "";
        }
        if (authoritySectorContainer) {
            authoritySectorContainer.classList.remove("opacity-50", "pointer-events-none");
        }
    };

    scopeSelect.addEventListener("change", () => {
        toggleEntityField();
        filterEntitiesByCategories();
    });

    if (sectorSelect) {
        sectorSelect.addEventListener("change", () => {
            filterSubsectorsBySector();
            filterCategoriesBySubsector();
            filterEntitiesByCategories();
        });
    }

    if (subsectorSelect) {
        subsectorSelect.addEventListener("change", () => {
            filterCategoriesBySubsector();
            filterEntitiesByCategories();
        });
    }

    if (categorySelect) {
        categorySelect.addEventListener("change", filterEntitiesByCategories);
    }

    if (roleSelect && viewerProfileContainer) {
        roleSelect.addEventListener("change", toggleViewerProfileField);
        roleSelect.addEventListener("change", toggleScopeByViewerType);
        roleSelect.addEventListener("change", toggleValidationPermissionsSection);
        toggleViewerProfileField();
    }
    if (viewerProfileSelect) {
        viewerProfileSelect.addEventListener("change", toggleScopeByViewerType);
    }

    toggleEntityField();
    filterSubsectorsBySector();
    filterCategoriesBySubsector();
    filterEntitiesByCategories();
    toggleScopeByViewerType();
    toggleValidationPermissionsSection();
})();
