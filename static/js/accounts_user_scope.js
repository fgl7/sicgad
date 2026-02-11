(() => {
    const scopeSelect = document.getElementById("id_scope_mode");
    const entitySelect = document.getElementById("id_entity");
    const entityContainer = document.querySelector("[data-entity-container]");

    if (!scopeSelect || !entitySelect || !entityContainer) {
        return;
    }

    const toggleEntityField = () => {
        const isGlobalCategory = scopeSelect.value === "CATEGORY_GLOBAL";
        entityContainer.classList.toggle("opacity-50", isGlobalCategory);
        entityContainer.classList.toggle("pointer-events-none", isGlobalCategory);

        if (isGlobalCategory) {
            entitySelect.value = "";
        }
    };

    scopeSelect.addEventListener("change", toggleEntityField);
    toggleEntityField();
})();
