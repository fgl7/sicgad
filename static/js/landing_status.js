(() => {
    const badge = document.querySelector('[data-system-status]');
    if (!badge) {
        return;
    }

    const label = badge.querySelector('[data-status-label]');
    const setState = (state) => {
        badge.classList.remove('is-online', 'is-offline');
        badge.classList.add(state);
        if (label) {
            label.textContent = state === 'is-online' ? 'Sistema en línea' : 'Modo sin conexión';
        }
        badge.setAttribute('aria-label', label ? label.textContent : 'Estado del sistema');
    };

    const updateFromNavigator = () => {
        if (navigator.onLine) {
            setState('is-online');
            return;
        }
        setState('is-offline');
    };

    window.addEventListener('online', updateFromNavigator);
    window.addEventListener('offline', updateFromNavigator);
    updateFromNavigator();
})();
