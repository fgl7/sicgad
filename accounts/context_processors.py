from django.db.utils import OperationalError, ProgrammingError

from .models import Membership


def admin_flags(request):
    user = getattr(request, "user", None)

    is_admin = False
    is_loader = False
    is_validator = False
    pending_schema_requests = 0
    pending_validation_items = 0
    pending_certification_alerts = 0
    loader_pending_certification_alerts = 0
    loader_validation_approved = 0
    loader_validation_rejected = 0
    loader_certification_rejected = 0
    loader_schema_approved = 0
    loader_schema_rejected = 0
    loader_default_entity = None

    if user and user.is_authenticated:
        try:
            if user.is_superuser:
                is_admin = True
            else:
                memberships = Membership.objects.filter(user=user, is_active=True).select_related("entity")
                is_admin = memberships.filter(role="ADMIN").exists()
                is_loader = memberships.filter(role="LOADER").exists()
                is_validator = memberships.filter(role="VALIDATOR").exists()

                loader_membership = memberships.filter(role="LOADER", entity__isnull=False).first()
                if loader_membership:
                    loader_default_entity = loader_membership.entity
        except (OperationalError, ProgrammingError):
            is_admin = False
            is_loader = False
            is_validator = False

    path = getattr(request, "path", "") or ""
    if path.startswith("/schemas/"):
        current_section = "Esquemas"
    elif path.startswith("/ingest/"):
        current_section = "Carga de datos"
    elif path.startswith("/validate/"):
        current_section = "Validacion"
    elif path.startswith("/accounts/"):
        current_section = "Usuarios y roles"
    elif path.startswith("/audit/"):
        current_section = "Auditoria"
    elif path.startswith("/performance/"):
        current_section = "Desempeno"
    elif path.startswith("/structure/"):
        current_section = "Clasificacion"
    elif path.startswith("/home/"):
        current_section = "Inicio"
    else:
        current_section = "Inicio"

    return {
        "is_admin": is_admin,
        "is_loader": is_loader,
        "is_validator": is_validator,
        "current_section": current_section,
        "pending_schema_requests": pending_schema_requests,
        "pending_validation_items": pending_validation_items,
        "pending_certification_alerts": pending_certification_alerts,
        "loader_pending_certification_alerts": loader_pending_certification_alerts,
        "loader_validation_approved": loader_validation_approved,
        "loader_validation_rejected": loader_validation_rejected,
        "loader_certification_rejected": loader_certification_rejected,
        "loader_schema_approved": loader_schema_approved,
        "loader_schema_rejected": loader_schema_rejected,
        "loader_default_entity": loader_default_entity,
        # Compatibilidad temporal para plantillas antiguas.
        "loader_default_plant": loader_default_entity,
        "loader_default_project": None,
    }
