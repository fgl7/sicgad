(() => {
    const toggles = document.querySelectorAll('[data-toggle-password]');
    if (!toggles.length) return;

    toggles.forEach((toggle) => {
        const targetId = toggle.getAttribute('data-toggle-password');
        const input = targetId ? document.getElementById(targetId) : null;
        if (!input) return;

        const setState = (revealed) => {
            toggle.classList.toggle('is-active', revealed);
            toggle.setAttribute('aria-label', revealed ? 'Ocultar contrasena' : 'Mostrar contrasena');
        };

        toggle.addEventListener('click', () => {
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            setState(isPassword);
            input.focus();
        });

        setState(false);
    });
})();
