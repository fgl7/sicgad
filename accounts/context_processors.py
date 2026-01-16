from django.db.models import Q, Exists, OuterRef
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .models import Membership
from schemas.models import DatasetType
from schemas.services import ensure_previous_month_consolidated, previous_month_range
from ingest.models import DatasetInstance
from validation.models import ValidationAction
from validation.services import sync_previous_month_certifications


def admin_flags(request):
    user = getattr(request, "user", None)
    is_admin = False
    is_loader = False
    is_validator = False
    pending_schema_requests = 0
    pending_validation_items = 0
    loader_validation_approved = 0
    loader_validation_rejected = 0
    loader_certification_rejected = 0
    loader_schema_approved = 0
    loader_schema_rejected = 0
    loader_default_plant = None
    loader_default_project = None
    pending_certification_alerts = 0
    loader_pending_certification_alerts = 0
    loader_plants_ids = []
    loader_projects_ids = []
    loader_memberships_list = []
    has_global_loader = False
    if user and user.is_authenticated:
        ensure_previous_month_consolidated()
        sync_previous_month_certifications()
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()
            loader_memberships = Membership.objects.filter(
                user=user,
                role="LOADER",
                is_active=True,
            ).select_related("plant", "project")
            loader_memberships_list = list(loader_memberships)
            is_loader = bool(loader_memberships_list)
            is_validator = Membership.objects.filter(
                user=user, role="VALIDATOR", is_active=True
            ).exists()

            profile = getattr(user, "profile", None)

            if is_loader:
                loader_plants_ids = [m.plant_id for m in loader_memberships_list if m.plant_id]
                loader_projects_ids = [m.project_id for m in loader_memberships_list if m.project_id]
                has_global_loader = any(
                    m.plant_id is None and m.project_id is None for m in loader_memberships_list
                )
                loader_membership = next(
                    (
                        m
                        for m in loader_memberships_list
                        if m.plant_id is not None or m.project_id is not None
                    ),
                    loader_memberships_list[0],
                )
                loader_default_plant = loader_membership.plant if loader_membership.plant_id else None
                loader_default_project = (
                    loader_membership.project if loader_membership.project_id else None
                )

                _, prev_month_end = previous_month_range()
                loader_cert_states = [DatasetInstance.STATE_DRAFT]
                loader_cert_qs = DatasetInstance.objects.filter(
                    dataset_type__validation_frequency=DatasetType.MONTHLY,
                    dataset_type__is_certification=True,
                    period=prev_month_end,
                    state__in=loader_cert_states,
                    last_error_summary="",
                )
                if not has_global_loader:
                    if loader_plants_ids:
                        loader_cert_qs = loader_cert_qs.filter(plant_id__in=loader_plants_ids)
                    else:
                        loader_cert_qs = loader_cert_qs.none()
                if profile and profile.last_seen_certification_alert:
                    loader_cert_qs = loader_cert_qs.filter(
                        updated_at__gt=profile.last_seen_certification_alert
                    )
                loader_pending_certification_alerts = loader_cert_qs.count()

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
                ).select_related("plant", "project")
                weekly_memberships = Membership.objects.filter(
                    user=user,
                    role="VALIDATOR",
                    is_active=True,
                    can_validate_weekly=True,
                ).select_related("plant", "project")
                projections_memberships = Membership.objects.filter(
                    user=user,
                    role="VALIDATOR",
                    is_active=True,
                    can_validate_projections=True,
                ).select_related("plant", "project")
                monthly_memberships = Membership.objects.filter(
                    user=user,
                    role="VALIDATOR",
                    is_active=True,
                    can_validate_monthly=True,
                ).select_related("plant", "project")

                daily_plants = [m.plant_id for m in daily_memberships if m.plant_id]
                weekly_plants = [m.plant_id for m in weekly_memberships if m.plant_id]
                projections_plants = [m.plant_id for m in projections_memberships if m.plant_id]
                monthly_plants = [m.plant_id for m in monthly_memberships if m.plant_id]

                daily_projects = [m.project_id for m in daily_memberships if m.project_id]
                weekly_projects = [m.project_id for m in weekly_memberships if m.project_id]
                projections_projects = [
                    m.project_id for m in projections_memberships if m.project_id
                ]
                monthly_projects = [m.project_id for m in monthly_memberships if m.project_id]

                has_global_daily = any(
                    m.plant_id is None and m.project_id is None for m in daily_memberships
                )
                has_global_weekly = any(
                    m.plant_id is None and m.project_id is None for m in weekly_memberships
                )
                has_global_projections = any(
                    m.plant_id is None and m.project_id is None for m in projections_memberships
                )
                has_global_monthly = any(
                    m.plant_id is None and m.project_id is None for m in monthly_memberships
                )

                base_qs = DatasetInstance.objects.filter(
                    state__in=[
                        DatasetInstance.STATE_SUBMITTED,
                        DatasetInstance.STATE_VALIDATED_L1,
                    ]
                )

                def _build_freq_scope(freq, plant_ids, project_ids, has_global):
                    if has_global:
                        return Q(dataset_type__validation_frequency=freq)
                    scope_filter = Q()
                    if plant_ids:
                        scope_filter |= Q(
                            dataset_type__validation_frequency=freq,
                            plant_id__in=plant_ids,
                        )
                    if project_ids:
                        scope_filter |= Q(
                            dataset_type__validation_frequency=freq,
                            project_id__in=project_ids,
                        )
                    if not plant_ids and not project_ids:
                        scope_filter = Q(pk__in=[])
                    return scope_filter

                daily_filter = _build_freq_scope(
                    DatasetType.DAILY,
                    daily_plants,
                    daily_projects,
                    has_global_daily,
                )
                weekly_filter = _build_freq_scope(
                    DatasetType.WEEKLY,
                    weekly_plants,
                    weekly_projects,
                    has_global_weekly,
                )
                monthly_filter = _build_freq_scope(
                    DatasetType.MONTHLY,
                    monthly_plants,
                    monthly_projects,
                    has_global_monthly,
                )
                projections_filter = _build_freq_scope(
                    DatasetType.FLEXIBLE,
                    projections_plants,
                    projections_projects,
                    has_global_projections,
                )

                pending_validation_items = base_qs.filter(
                    daily_filter | weekly_filter | projections_filter | monthly_filter
                ).count()

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

                    profile = getattr(user, "profile", None)
                    last_seen_cert = profile.last_seen_certification_alert if profile else None
                    cert_qs = cert_qs.filter(
                        state__in=[
                            DatasetInstance.STATE_SUBMITTED,
                            DatasetInstance.STATE_VALIDATED_L1,
                            DatasetInstance.STATE_VALIDATED_L2,
                            DatasetInstance.STATE_LOCKED,
                        ]
                    )

                    approval_subquery = ValidationAction.objects.filter(
                        dataset_instance=OuterRef("pk"),
                        user=user,
                        decision=ValidationAction.DECISION_APPROVE,
                    )
                    approval_since_submit = approval_subquery.filter(
                        created_at__gte=OuterRef("submitted_at")
                    )
                    cert_qs = cert_qs.annotate(
                        already_approved_history=Exists(approval_subquery),
                        already_approved_recent=Exists(approval_since_submit),
                    ).filter(
                        Q(submitted_at__isnull=True, already_approved_history=False)
                        | Q(submitted_at__isnull=False, already_approved_recent=False)
                    )
                    if last_seen_cert:
                        cert_qs = cert_qs.filter(updated_at__gt=last_seen_cert)
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
                # Certificaciones rechazadas (pueden no estar asociadas al mismo usuario)
                cert_rejected_qs = DatasetInstance.objects.filter(
                    dataset_type__validation_frequency=DatasetType.MONTHLY,
                    dataset_type__is_certification=True,
                    state=DatasetInstance.STATE_DRAFT,
                    last_error_summary__gt="",
                    period__lte=prev_month_end if "prev_month_end" in locals() else timezone.now().date(),
                )
                if not has_global_loader:
                    if loader_plants_ids:
                        cert_rejected_qs = cert_rejected_qs.filter(plant_id__in=loader_plants_ids)
                    else:
                        cert_rejected_qs = cert_rejected_qs.none()
                if last_seen_validation:
                    cert_rejected_qs = cert_rejected_qs.filter(updated_at__gt=last_seen_validation)
                loader_certification_rejected = cert_rejected_qs.count()

                # Notificaciones sobre esquemas de sus plantas/proyectos aprobados y rechazados.
                # Para loaders globales (sin planta/proyecto asignado) se consideran todos.
                loader_plants = [pid for pid in loader_plants_ids if pid]
                loader_projects = [pid for pid in loader_projects_ids if pid]
                if loader_plants or loader_projects or has_global_loader:
                    prev_seen_schema = (
                        profile.last_seen_schema_status if profile else None
                    )
                    base_qs = DatasetType.objects.filter(
                        is_certification=False,
                    )
                    if not has_global_loader:
                        base_qs = base_qs.filter(
                            Q(plant_id__in=loader_plants) | Q(project_id__in=loader_projects)
                        )

                    # Aprobados: solo se muestran como "positivos nuevos" desde la
                    # última vez que el cargador revisó la sección de esquemas.
                    approved_qs = base_qs.filter(status=DatasetType.STATUS_APPROVED)
                    if prev_seen_schema:
                        approved_qs = approved_qs.filter(updated_at__gt=prev_seen_schema)
                    loader_schema_approved = approved_qs.count()

                    # Rechazados: persisten mientras sigan en estado REJECTED,
                    # independientemente de si el cargador ya vio la sección.
                    rejected_qs = base_qs.filter(status=DatasetType.STATUS_REJECTED)
                    loader_schema_rejected = rejected_qs.count()
        except (OperationalError, ProgrammingError):
            pending_schema_requests = 0
            pending_validation_items = 0
            pending_certification_alerts = 0
            loader_validation_approved = 0
            loader_validation_rejected = 0
            loader_schema_approved = 0
            loader_schema_rejected = 0

    path = getattr(request, "path", "") or ""

    # Si un cargador está viendo la sección de esquemas, marcamos la fecha/hora
    # como "vistos" para limpiar futuras alarmas positivas de aprobados.
    if path.startswith("/schemas/") and is_loader and not is_admin:
        try:
            profile = getattr(user, "profile", None)
        except (OperationalError, ProgrammingError):
            profile = None
        if profile:
            profile.last_seen_schema_status = timezone.now()
            profile.save(update_fields=["last_seen_schema_status"])

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
    elif path.startswith("/performance/"):
        current_section = "Desempeño"
    elif path.startswith("/projects/"):
        current_section = "Proyectos"
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
        "loader_default_plant": loader_default_plant,
        "loader_default_project": loader_default_project,
    }
