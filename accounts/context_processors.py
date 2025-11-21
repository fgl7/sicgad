from .models import Membership


def admin_flags(request):
    user = getattr(request, "user", None)
    is_admin = False
    is_loader = False
    is_validator = False
    if user and user.is_authenticated:
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()
            is_loader = Membership.objects.filter(user=user, role="LOADER", is_active=True).exists()
            is_validator = Membership.objects.filter(
                user=user, role="VALIDATOR", is_active=True
            ).exists()

    path = getattr(request, "path", "") or ""
    if path.startswith("/schemas/"):
        current_section = "Esquemas"
    elif path.startswith("/ingest/"):
        current_section = "Carga de datos"
    elif path.startswith("/validate/"):
        current_section = "Validación"
    elif path.startswith("/plants/"):
        current_section = "Plantas"
    elif path.startswith("/accounts/"):
        current_section = "Usuarios y roles"
    elif path.startswith("/audit/"):
        current_section = "Auditoría"
    elif path.startswith("/home/"):
        current_section = "Inicio"
    else:
        current_section = "Inicio"

    return {
        "is_admin": is_admin,
        "is_loader": is_loader,
        "is_validator": is_validator,
        "current_section": current_section,
    }
