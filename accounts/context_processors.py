from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .models import Membership
from schemas.models import DatasetType
from schemas.services import ensure_previous_month_consolidated, previous_month_range
from ingest.models import DatasetInstance


def admin_flags(request):
    user = getattr(request, "user", None)
    is_admin = False
    is_loader = False
    is_validator = False
    pending_schema_requests = 0
    pending_validation_items = 0
    loader_validation_approved = 0
    loader_validation_rejected = 0
    loader_schema_approved = 0
    loader_schema_rejected = 0
    loader_default_plant = None
    pending_certification_alerts = 0
    if user and user.is_authenticated:
        ensure_previous_month_consolidated()
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()
            is_loader = Membership.objects.filter(user=user, role="LOADER", is_active=True).exists()
            is_validator = Membership.objects.filter(
                user=user, role="VALIDATOR", is_active=True
            ).exists()

            profile = getattr(user, "profile", None)

            if is_loader:
                loader_membership = (
                    Membership.objects.filter(
                        user=user,
                        role="LOADER",
                        is_active=True,
                        plant__isnull=False,
                    )
                    .select_related("plant")
                    .first()
                )
                if loader_membership:
                    loader_default_plant = loader_membership.plant

        try:
            if is_admin:
                pending_schema_requests = DatasetType.objects.filter(
                    status=DatasetType.STATUS_PENDING
                ).count()

            # Conteo de items pendientes para cualquier usuario con rol de validador,
            # independientemente de si también tiene rol de administrador.
            if is_validator:
                daily_memberships = Membership.objects.filter(
                    user=user,
                    role="VALIDATOR",
                    is_active=True,
                    can_validate_daily=True,
                )
                monthly_memberships = Membership.objects.filter(
                    user=user,
                    role="VALIDATOR",
                    is_active=True,
                    can_validate_monthly=True,
                )

                daily_plants = [m.plant_id for m in daily_memberships if m.plant_id]
                monthly_plants = [m.plant_id for m in monthly_memberships if m.plant_id]

                has_global_daily = any(m.plant_id is None for m in daily_memberships)
                has_global_monthly = any(m.plant_id is None for m in monthly_memberships)

                base_qs = DatasetInstance.objects.filter(
                    state__in=[
                        DatasetInstance.STATE_SUBMITTED,
                        DatasetInstance.STATE_VALIDATED_L1,
                    ]
                )

                daily_filter = Q(
                    dataset_type__validation_frequency=DatasetType.DAILY,
                    plant_id__in=daily_plants,
                )
                if has_global_daily:
                    daily_filter |= Q(dataset_type__validation_frequency=DatasetType.DAILY)

                monthly_filter = Q(
                    dataset_type__validation_frequency=DatasetType.MONTHLY,
                    plant_id__in=monthly_plants,
                )
                if has_global_monthly:
                    monthly_filter |= Q(
                        dataset_type__validation_frequency=DatasetType.MONTHLY
                    )

                pending_validation_items = base_qs.filter(daily_filter | monthly_filter).count()

                if monthly_memberships.exists():
                    _, prev_month_end = previous_month_range()
                    pending_cert_states = [
                        DatasetInstance.STATE_DRAFT,
                        DatasetInstance.STATE_SUBMITTED,
                        DatasetInstance.STATE_VALIDATED_L1,
                        DatasetInstance.STATE_VALIDATED_L2,
                    ]
                    cert_qs = DatasetInstance.objects.filter(
                        dataset_type__validation_frequency=DatasetType.MONTHLY,
                        dataset_type__is_certification=True,
                        period=prev_month_end,
                        state__in=pending_cert_states,
                    )
                    if not has_global_monthly:
                        if monthly_plants:
                            cert_qs = cert_qs.filter(plant_id__in=monthly_plants)
                        else:
                            cert_qs = cert_qs.none()

                    pending_certification_alerts = cert_qs.count()

            if is_loader and not is_admin:
                # Notificaciones sobre cargas aprobadas y rechazadas
                loader_qs = DatasetInstance.objects.filter(created_by__user=user)
                last_seen_validation = profile.last_seen_validation_status if profile else None
                approved_qs = loader_qs.filter(state=DatasetInstance.STATE_PUBLISHED)
                rejected_qs = loader_qs.filter(
                    state=DatasetInstance.STATE_DRAFT,
                    last_error_summary__gt="",
                )
                if last_seen_validation:
                    approved_qs = approved_qs.filter(updated_at__gt=last_seen_validation)
                    rejected_qs = rejected_qs.filter(updated_at__gt=last_seen_validation)
                loader_validation_approved = approved_qs.count()
                loader_validation_rejected = rejected_qs.count()

                # Notificaciones sobre esquemas de sus plantas aprobados y rechazados
                loader_plants = list(
                    Membership.objects.filter(
                        user=user,
                        role="LOADER",
                        is_active=True,
                        plant__isnull=False,
                    ).values_list("plant_id", flat=True)
                )
                if loader_plants:
                    schema_qs = DatasetType.objects.filter(
                        plant_id__in=loader_plants,
                        is_certification=False,
                        status__in=[
                            DatasetType.STATUS_APPROVED,
                            DatasetType.STATUS_REJECTED,
                        ],
                    )
                    if profile and profile.last_seen_schema_status:
                        schema_qs = schema_qs.filter(
                            updated_at__gt=profile.last_seen_schema_status
                        )

                    loader_schema_approved = schema_qs.filter(
                        status=DatasetType.STATUS_APPROVED
                    ).count()
                    loader_schema_rejected = schema_qs.filter(
                        status=DatasetType.STATUS_REJECTED
                    ).count()
        except (OperationalError, ProgrammingError):
            pending_schema_requests = 0
            pending_validation_items = 0
            pending_certification_alerts = 0
            loader_validation_approved = 0
            loader_validation_rejected = 0
            loader_schema_approved = 0
            loader_schema_rejected = 0

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
        "pending_schema_requests": pending_schema_requests,
        "pending_validation_items": pending_validation_items,
        "pending_certification_alerts": pending_certification_alerts,
        "loader_validation_approved": loader_validation_approved,
        "loader_validation_rejected": loader_validation_rejected,
        "loader_schema_approved": loader_schema_approved,
        "loader_schema_rejected": loader_schema_rejected,
        "loader_default_plant": loader_default_plant,
    }
