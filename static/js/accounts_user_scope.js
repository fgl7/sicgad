(() => {
    const scopeSelect = document.getElementById("id_scope_mode");
    const entitySelect = document.getElementById("id_entity");
    const entityContainer = document.querySelector("[data-entity-container]");
    const roleSelect = document.getElementById("id_role");
    const viewerProfileContainer = document.querySelector("[data-viewer-profile-container]");
    const viewerProfileSelect = document.getElementById("id_viewer_profile_type");
    const standardScopeContainers = document.querySelectorAll("[data-standard-scope-container]");
    const authorityScopeContainer = document.querySelector("[data-authority-scope-container]");
    const authorityScopeSelect = document.getElementById("id_authority_scope_mode");
    const authoritySectorContainer = document.querySelector("[data-authority-sector-container]");
    const authoritySectorSelect = document.getElementById("id_authority_sector");

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

    const isAuthorityViewer = () => {
        if (!roleSelect || !viewerProfileSelect) {
            return false;
        }
        return roleSelect.value === "VIEWER" && viewerProfileSelect.value === "AUTHORITY_MHE";
    };

    const toggleAuthoritySectorField = () => {
        if (!authorityScopeSelect || !authoritySectorContainer || !authoritySectorSelect) {
            return;
        }
        const allSectors = authorityScopeSelect.value === "ALL_SECTORS";
        authoritySectorContainer.classList.toggle("opacity-50", allSectors);
        authoritySectorContainer.classList.toggle("pointer-events-none", allSectors);
        authoritySectorSelect.disabled = allSectors;
        if (allSectors) {
            authoritySectorSelect.value = "";
        }
    };

    const toggleScopeByViewerType = () => {
        const useAuthorityScope = isAuthorityViewer();

        standardScopeContainers.forEach((container) => {
            container.classList.toggle("hidden", useAuthorityScope);
        });

        if (authorityScopeContainer) {
            authorityScopeContainer.classList.toggle("hidden", !useAuthorityScope);
        }

        if (scopeSelect) {
            scopeSelect.disabled = useAuthorityScope;
        }
        if (entitySelect) {
            entitySelect.disabled = useAuthorityScope || entityContainer.classList.contains("pointer-events-none");
            if (useAuthorityScope) {
                entitySelect.value = "";
            }
        }

        if (authorityScopeSelect) {
            authorityScopeSelect.disabled = !useAuthorityScope;
        }
        if (authoritySectorSelect) {
            authoritySectorSelect.disabled = !useAuthorityScope;
            if (!useAuthorityScope) {
                authorityScopeSelect && (authorityScopeSelect.value = "SECTOR");
                authoritySectorSelect.value = "";
            }
        }

        if (useAuthorityScope) {
            toggleAuthoritySectorField();
        }
    };

    scopeSelect.addEventListener("change", toggleEntityField);
    toggleEntityField();

    if (roleSelect && viewerProfileContainer) {
        roleSelect.addEventListener("change", toggleViewerProfileField);
        roleSelect.addEventListener("change", toggleScopeByViewerType);
        toggleViewerProfileField();
    }
    if (viewerProfileSelect) {
        viewerProfileSelect.addEventListener("change", toggleScopeByViewerType);
    }
    if (authorityScopeSelect) {
        authorityScopeSelect.addEventListener("change", toggleAuthoritySectorField);
    }
    toggleScopeByViewerType();
})();
