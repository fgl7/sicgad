from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render

from accounts.models import Membership
from audit.models import AuditLog
from ingest.models import DatasetInstance, PublishedDataPoint
from ingest.utils import _read_instance_file
from schemas.models import DatasetType, ColumnDef


def landing(request):
    return render(request, "landing.html")


@login_required
def home(request):
    user = request.user
    is_admin = False
    if user.is_authenticated:
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()

    # Estado rápido: algunos contadores básicos
    total_schemas = DatasetType.objects.count()
    total_instances = DatasetInstance.objects.count()
    pending_instances = DatasetInstance.objects.filter(
        state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1]
    ).count()
    published_instances = DatasetInstance.objects.filter(state=DatasetInstance.STATE_PUBLISHED).count()

    # Últimas acciones de auditoría (visibles para todos por transparencia)
    recent_logs = AuditLog.objects.select_related("user").order_by("-created_at")[:10]

    # Últimas cargas de datos (independiente del estado)
    recent_instances = (
        DatasetInstance.objects.select_related("dataset_type", "plant")
        .order_by("-created_at")[:5]
    )

    return render(
        request,
        "kpis/home.html",
        {
            "is_admin": is_admin,
            "total_schemas": total_schemas,
            "total_instances": total_instances,
            "pending_instances": pending_instances,
            "published_instances": published_instances,
            "recent_logs": recent_logs,
        "recent_instances": recent_instances,
        },
    )


def _get_role_flags(user):
    if not user.is_authenticated:
        return False, False, False, False
    is_admin = user.is_superuser or Membership.objects.filter(
        user=user, role="ADMIN", is_active=True
    ).exists()
    is_loader = Membership.objects.filter(user=user, role="LOADER", is_active=True).exists()
    is_validator = Membership.objects.filter(user=user, role="VALIDATOR", is_active=True).exists()
    is_viewer = Membership.objects.filter(user=user, role="VIEWER", is_active=True).exists()
    return is_admin, is_loader, is_validator, is_viewer


@login_required
def charts(request):
    user = request.user
    is_admin, is_loader, is_validator, is_viewer = _get_role_flags(user)

    instances = DatasetInstance.objects.select_related("dataset_type", "plant")

    if not is_admin:
        memberships = Membership.objects.filter(user=user, is_active=True)
        plant_ids = list(memberships.exclude(plant__isnull=True).values_list("plant_id", flat=True))
        has_global = memberships.filter(plant__isnull=True).exists()
        if plant_ids and not has_global:
            instances = instances.filter(plant_id__in=plant_ids)
        elif not plant_ids and not has_global:
            instances = instances.none()

    published_states = [DatasetInstance.STATE_PUBLISHED, DatasetInstance.STATE_LOCKED]
    published_instances = instances.filter(state__in=published_states).order_by(
        "plant__code", "dataset_type__name", "period"
    )

    can_see_drafts = is_admin or is_loader or is_validator
    if can_see_drafts:
        draft_instances = instances.exclude(state__in=published_states).order_by(
            "plant__code", "dataset_type__name", "period"
        )
    else:
        draft_instances = DatasetInstance.objects.none()

    return render(
        request,
        "kpis/charts.html",
        {
            "published_instances": published_instances,
            "draft_instances": draft_instances,
            "can_see_drafts": can_see_drafts,
        },
    )


@login_required
def dataset_data(request, instance_id: int):
    user = request.user
    is_admin, is_loader, is_validator, is_viewer = _get_role_flags(user)

    instance = get_object_or_404(
        DatasetInstance.objects.select_related("dataset_type", "plant"),
        pk=instance_id,
    )

    # Permisos por planta
    if not is_admin:
        memberships = Membership.objects.filter(user=user, is_active=True)
        plant_ids = list(memberships.exclude(plant__isnull=True).values_list("plant_id", flat=True))
        has_global = memberships.filter(plant__isnull=True).exists()
        if not (has_global or (plant_ids and instance.plant_id in plant_ids)):
            raise Http404

    published_states = [DatasetInstance.STATE_PUBLISHED, DatasetInstance.STATE_LOCKED]

    source = request.GET.get("source", "auto")
    if source not in ("auto", "draft", "published"):
        source = "auto"

    if source == "draft":
        if not (is_admin or is_loader or is_validator):
            raise Http404
        use_published = False
    elif source == "published":
        if instance.state not in published_states:
            raise Http404
        use_published = True
    else:  # auto
        use_published = instance.state in published_states
        if use_published and not (is_admin or is_loader or is_validator or is_viewer):
            raise Http404
        if not use_published and not (is_admin or is_loader or is_validator):
            raise Http404

    dataset = instance.dataset_type
    columns_qs = dataset.columns.filter(is_active=True).order_by("display_order", "name")

    columns = [
        {
            "id": col.id,
            "name": col.name,
            "label": col.label,
            "data_type": col.data_type,
            "axis_role": col.axis_role,
            "unit": col.unit,
            "default_agg": col.default_agg,
            "is_primary_kpi": col.is_primary_kpi,
        }
        for col in columns_qs
    ]

    if use_published:
        points = (
            PublishedDataPoint.objects.filter(instance=instance)
            .select_related("column")
            .order_by("row_index", "column__display_order", "column__name")
        )

        rows_map = {}
        for p in points:
            row = rows_map.setdefault(p.row_index, {})
            if p.numeric_value is not None:
                value = p.numeric_value
            elif p.date_value is not None:
                value = p.date_value.isoformat()
            elif p.bool_value is not None:
                value = bool(p.bool_value)
            else:
                value = p.text_value
            row[p.column.name] = value

        rows = [
            {"row_index": idx, "values": row}
            for idx, row in sorted(rows_map.items(), key=lambda item: item[0])
        ]
    else:
        header, parsed_rows = _read_instance_file(instance)

        header_map = {}
        for col in columns_qs:
            key = (col.label or col.name or "").strip().lower()
            if key:
                header_map[key] = col.name

        name_by_index = []
        for name in header:
            key = (name or "").strip().lower()
            name_by_index.append(header_map.get(key))

        rows = []
        for row in parsed_rows:
            values = {}
            for idx, raw in enumerate(row.values):
                col_name = name_by_index[idx] if idx < len(name_by_index) else None
                if not col_name:
                    continue
                values[col_name] = raw
            rows.append({"row_index": row.row_index, "values": values})

    data = {
        "instance": {
            "id": instance.id,
            "plant_code": instance.plant.code,
            "plant_name": instance.plant.name,
            "dataset_name": dataset.name,
            "period": instance.period.isoformat(),
            "state": instance.state,
            "is_published": instance.state in published_states,
            "is_certification": dataset.is_certification,
            "validation_frequency": dataset.validation_frequency,
        },
        "columns": columns,
        "rows": rows,
    }

    return JsonResponse(data)
