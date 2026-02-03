(() => {
    const toggles = document.querySelectorAll('[data-toggle-password]');
    if (!toggles.length) {
        return;
    }

    toggles.forEach((toggle) => {
        const targetId = toggle.getAttribute('data-toggle-password');
        let input = targetId ? document.getElementById(targetId) : null;
        if (!input) {
            const container = toggle.closest('.login-field, .force-input-wrap, .force-field') || toggle.parentElement;
            if (container) {
                input = container.querySelector('input');
            }
        }
        if (!input) {
            return;
        }

        const setState = (revealed) => {
            toggle.classList.toggle('is-active', revealed);
            toggle.setAttribute('aria-label', revealed ? 'Ocultar contraseña' : 'Mostrar contraseña');
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
