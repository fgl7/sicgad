from django.db.models import Exists, OuterRef, Q
from django.db.utils import OperationalError, ProgrammingError

from structure.models import Category, Sector
from .models import AccountProfile, Membership


def _validator_pending_items_count(user, memberships):
    from ingest.models import DatasetInstance
    from schemas.models import DatasetType
    from validation.models import ValidationAction

    daily_memberships = memberships.filter(role="VALIDATOR", can_validate_daily=True)
    weekly_memberships = memberships.filter(role="VALIDATOR", can_validate_weekly=True)
    projections_memberships = memberships.filter(role="VALIDATOR", can_validate_projections=True)
    monthly_memberships = memberships.filter(role="VALIDATOR", can_validate_monthly=True)

    daily_entities = [m.entity_id for m in daily_memberships if m.entity_id]
    weekly_entities = [m.entity_id for m in weekly_memberships if m.entity_id]
    projections_entities = [m.entity_id for m in projections_memberships if m.entity_id]
    monthly_entities = [m.entity_id for m in monthly_memberships if m.entity_id]

    has_global_daily = any(m.entity_id is None for m in daily_memberships)
    has_global_weekly = any(m.entity_id is None for m in weekly_memberships)
    has_global_projections = any(m.entity_id is None for m in projections_memberships)
    has_global_monthly = any(m.entity_id is None for m in monthly_memberships)

    daily_filter = Q(dataset_type__validation_frequency=DatasetType.DAILY)
    if not has_global_daily:
        daily_filter = daily_filter & Q(entity_id__in=daily_entities) if daily_entities else Q(pk__in=[])

    weekly_filter = Q(dataset_type__validation_frequency=DatasetType.WEEKLY)
    if not has_global_weekly:
        weekly_filter = weekly_filter & Q(entity_id__in=weekly_entities) if weekly_entities else Q(pk__in=[])

    projections_filter = Q(dataset_type__validation_frequency=DatasetType.FLEXIBLE)
    if not has_global_projections:
        projections_filter = (
            projections_filter & Q(entity_id__in=projections_entities)
            if projections_entities
            else Q(pk__in=[])
        )

    monthly_filter = Q(dataset_type__validation_frequency=DatasetType.MONTHLY)
    if not has_global_monthly:
        monthly_filter = monthly_filter & Q(entity_id__in=monthly_entities) if monthly_entities else Q(pk__in=[])

    approval_subquery = ValidationAction.objects.filter(
        dataset_instance=OuterRef("pk"),
        user=user,
        decision=ValidationAction.DECISION_APPROVE,
    )
    approval_since_submit = approval_subquery.filter(created_at__gte=OuterRef("submitted_at"))

    return (
        DatasetInstance.objects.filter(
            state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1]
        )
        .filter(daily_filter | weekly_filter | projections_filter | monthly_filter)
        .annotate(
            already_approved_history=Exists(approval_subquery),
            already_approved_recent=Exists(approval_since_submit),
        )
        .filter(
            Q(submitted_at__isnull=True, already_approved_history=False)
            | Q(submitted_at__isnull=False, already_approved_recent=False)
        )
        .count()
    )


def admin_flags(request):
    user = getattr(request, "user", None)

    is_admin = False
    is_loader = False
    is_validator = False
    is_viewer = False
    viewer_profile_type = AccountProfile.VIEWER_STANDARD
    is_authority_viewer = False
    is_external_monthly_viewer = False
    authority_viewer_has_global_scope = False
    viewer_nav_sectors = []
    authority_nav_tree = []
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
            from ingest.models import DatasetInstance
            from schemas.models import DatasetType
            from schemas.services import previous_month_range

            if user.is_superuser:
                is_admin = True
                pending_schema_requests = DatasetType.objects.filter(
                    status=DatasetType.STATUS_PENDING,
                    is_certification=False,
                ).count()
            else:
                memberships = Membership.objects.filter(user=user, is_active=True).select_related("entity")
                is_admin = memberships.filter(role="ADMIN").exists()
                is_loader = memberships.filter(role="LOADER").exists()
                is_validator = memberships.filter(role="VALIDATOR").exists()
                is_viewer = memberships.filter(role="VIEWER").exists()
                profile = getattr(user, "profile", None)
                if profile:
                    viewer_profile_type = profile.viewer_profile_type or AccountProfile.VIEWER_STANDARD
                is_authority_viewer = (
                    is_viewer
                    and viewer_profile_type == AccountProfile.VIEWER_AUTHORITY_MHE
                    and not is_admin
                    and not is_loader
                    and not is_validator
                )
                is_external_monthly_viewer = (
                    is_viewer
                    and viewer_profile_type == AccountProfile.VIEWER_EXTERNAL_MONTHLY
                    and not is_admin
                    and not is_loader
                    and not is_validator
                )
                if is_authority_viewer:
                    viewer_memberships = memberships.filter(role="VIEWER")
                    has_global_viewer = viewer_memberships.filter(entity__isnull=True).exists()
                    authority_viewer_has_global_scope = has_global_viewer
                    sector_qs = Sector.objects.filter(is_active=True)
                    if not has_global_viewer:
                        sector_ids = (
                            viewer_memberships.exclude(entity__isnull=True)
                            .values_list("entity__category__subsector__sector_id", flat=True)
                            .distinct()
                        )
                        sector_qs = sector_qs.filter(id__in=sector_ids)
                    viewer_nav_sectors = list(
                        sector_qs.order_by("name").values("id", "name")
                    )
                    if has_global_viewer:
                        category_qs = (
                            Category.objects.filter(
                                is_active=True,
                                subsector__is_active=True,
                                subsector__sector__is_active=True,
                            )
                            .select_related("subsector__sector")
                            .order_by(
                                "subsector__sector__name",
                                "subsector__name",
                                "name",
                            )
                        )
                    else:
                        viewer_entity_ids = list(
                            viewer_memberships.exclude(entity__isnull=True).values_list("entity_id", flat=True)
                        )
                        category_qs = (
                            Category.objects.filter(
                                is_active=True,
                                subsector__is_active=True,
                                subsector__sector__is_active=True,
                                entities__is_active=True,
                                entities__id__in=viewer_entity_ids,
                            )
                            .select_related("subsector__sector")
                            .distinct()
                            .order_by(
                                "subsector__sector__name",
                                "subsector__name",
                                "name",
                            )
                        )

                    tree_map = {}
                    for category in category_qs:
                        subsector = category.subsector
                        sector = subsector.sector
                        sector_node = tree_map.setdefault(
                            sector.id,
                            {"id": sector.id, "name": sector.name, "subsectors": {}},
                        )
                        subsector_node = sector_node["subsectors"].setdefault(
                            subsector.id,
                            {"id": subsector.id, "name": subsector.name, "categories": []},
                        )
                        subsector_node["categories"].append(
                            {"id": category.id, "name": category.name}
                        )

                    authority_nav_tree = []
                    for sector_node in tree_map.values():
                        subsectors = []
                        for subsector_node in sector_node["subsectors"].values():
                            subsector_node["categories"].sort(
                                key=lambda c: (c["name"] or "").lower()
                            )
                            subsectors.append(
                                {
                                    "id": subsector_node["id"],
                                    "name": subsector_node["name"],
                                    "categories": subsector_node["categories"],
                                }
                            )
                        subsectors.sort(key=lambda s: (s["name"] or "").lower())
                        authority_nav_tree.append(
                            {
                                "id": sector_node["id"],
                                "name": sector_node["name"],
                                "subsectors": subsectors,
                            }
                        )
                    authority_nav_tree.sort(key=lambda s: (s["name"] or "").lower())

                loader_memberships = memberships.filter(role="LOADER")
                loader_membership = loader_memberships.filter(entity__isnull=False).first()
                if loader_membership:
                    loader_default_entity = loader_membership.entity

                if is_admin:
                    pending_schema_requests = DatasetType.objects.filter(
                        status=DatasetType.STATUS_PENDING,
                        is_certification=False,
                    ).count()

                if is_validator:
                    pending_validation_items = _validator_pending_items_count(user, memberships)

                profile = getattr(user, "profile", None)

                if is_loader:
                    has_global_loader = loader_memberships.filter(entity__isnull=True).exists()
                    loader_entity_ids = list(
                        loader_memberships.exclude(entity__isnull=True).values_list("entity_id", flat=True)
                    )

                    schema_qs = DatasetType.objects.filter(
                        is_certification=False,
                        status__in=[DatasetType.STATUS_APPROVED, DatasetType.STATUS_REJECTED],
                    )
                    if not has_global_loader:
                        if loader_entity_ids:
                            schema_qs = schema_qs.filter(entity_id__in=loader_entity_ids)
                        else:
                            schema_qs = schema_qs.none()
                    if profile and profile.last_seen_schema_status:
                        schema_qs = schema_qs.filter(updated_at__gt=profile.last_seen_schema_status)
                    loader_schema_approved = schema_qs.filter(status=DatasetType.STATUS_APPROVED).count()
                    loader_schema_rejected = schema_qs.filter(status=DatasetType.STATUS_REJECTED).count()

                    validation_qs = DatasetInstance.objects.filter(created_by__user=user)
                    if profile and profile.last_seen_validation_status:
                        validation_qs = validation_qs.filter(updated_at__gt=profile.last_seen_validation_status)
                    loader_validation_approved = validation_qs.filter(
                        state__in=[DatasetInstance.STATE_PUBLISHED, DatasetInstance.STATE_LOCKED]
                    ).count()
                    loader_validation_rejected = validation_qs.filter(
                        state=DatasetInstance.STATE_DRAFT,
                        last_error_summary__gt="",
                    ).count()

                    _, prev_month_end = previous_month_range()
                    cert_qs = DatasetInstance.objects.filter(
                        dataset_type__validation_frequency=DatasetType.MONTHLY,
                        dataset_type__is_certification=True,
                        period=prev_month_end,
                        state=DatasetInstance.STATE_DRAFT,
                    )
                    if not has_global_loader:
                        if loader_entity_ids:
                            cert_qs = cert_qs.filter(entity_id__in=loader_entity_ids)
                        else:
                            cert_qs = cert_qs.none()
                    if profile and profile.last_seen_certification_alert:
                        cert_qs = cert_qs.filter(updated_at__gt=profile.last_seen_certification_alert)
                    loader_pending_certification_alerts = cert_qs.filter(last_error_summary="").count()
                    loader_certification_rejected = cert_qs.filter(last_error_summary__gt="").count()

                if is_validator:
                    _, prev_month_end = previous_month_range()
                    pending_cert_states = [
                        DatasetInstance.STATE_SUBMITTED,
                        DatasetInstance.STATE_VALIDATED_L1,
                        DatasetInstance.STATE_VALIDATED_L2,
                        DatasetInstance.STATE_LOCKED,
                    ]
                    validator_monthly_memberships = memberships.filter(
                        role="VALIDATOR",
                        can_validate_monthly=True,
                    )
                    has_global_monthly = validator_monthly_memberships.filter(entity__isnull=True).exists()
                    monthly_entity_ids = list(
                        validator_monthly_memberships.exclude(entity__isnull=True).values_list("entity_id", flat=True)
                    )
                    cert_alerts_qs = DatasetInstance.objects.filter(
                        dataset_type__validation_frequency=DatasetType.MONTHLY,
                        dataset_type__is_certification=True,
                        period=prev_month_end,
                        state__in=pending_cert_states,
                    )
                    if not has_global_monthly:
                        if monthly_entity_ids:
                            cert_alerts_qs = cert_alerts_qs.filter(entity_id__in=monthly_entity_ids)
                        else:
                            cert_alerts_qs = cert_alerts_qs.none()
                    if profile and profile.last_seen_certification_alert:
                        cert_alerts_qs = cert_alerts_qs.filter(updated_at__gt=profile.last_seen_certification_alert)
                    pending_certification_alerts = cert_alerts_qs.count()
        except (OperationalError, ProgrammingError):
            is_admin = False
            is_loader = False
            is_validator = False
            is_viewer = False

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
        "is_viewer": is_viewer,
        "viewer_profile_type": viewer_profile_type,
        "is_authority_viewer": is_authority_viewer,
        "is_external_monthly_viewer": is_external_monthly_viewer,
        "authority_viewer_has_global_scope": authority_viewer_has_global_scope,
        "viewer_nav_sectors": viewer_nav_sectors,
        "authority_nav_tree": authority_nav_tree,
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
    }
