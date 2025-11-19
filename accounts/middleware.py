from django.shortcuts import redirect
from django.urls import reverse


class PasswordChangeRequiredMiddleware:
    """
    Si el perfil del usuario tiene must_change_password=True,
    redirige siempre a la vista de cambio de contraseña obligatoria,
    excepto en las rutas necesarias para poder iniciar sesión y cambiarla.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            profile = getattr(user, "profile", None)
            if profile and profile.must_change_password:
                path = request.path
                allowed_prefixes = (
                    "/static/",
                    "/admin/login",
                    "/admin/logout",
                    "/accounts/password-change",
                )

                if any(path.startswith(p) for p in allowed_prefixes):
                    return self.get_response(request)

                # Permitir también la vista de login normal
                if path.startswith("/login"):
                    return self.get_response(request)

                return redirect("accounts:force_password_change")

        return self.get_response(request)
