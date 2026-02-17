from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render

from accounts.models import AccountProfile, Membership
from audit.models import AuditLog
from ingest.models import DatasetInstance, PublishedDataPoint
from performance.models import PerformanceIndicator, PerformanceIndicatorResult
from ingest.utils import _read_instance_file
from schemas.models import DatasetType


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
        DatasetInstance.objects.select_related("dataset_type", "entity")
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


def _get_viewer_profile_type(user):
    profile = getattr(user, "profile", None)
    if not profile:
        return AccountProfile.VIEWER_STANDARD
    return profile.viewer_profile_type or AccountProfile.VIEWER_STANDARD


def _apply_membership_scope(user, is_admin, datasets):
    if is_admin:
        return datasets
    memberships = Membership.objects.filter(user=user, is_active=True)
    entity_ids = list(memberships.exclude(entity__isnull=True).values_list("entity_id", flat=True))
    has_global = memberships.filter(entity__isnull=True).exists()
    if entity_ids and not has_global:
        return datasets.filter(entity_id__in=entity_ids)
    if not entity_ids and not has_global:
        return datasets.none()
    return datasets


def _group_datasets_for_authority(datasets):
    grouped = {}
    for ds in datasets.select_related("entity__category__subsector__sector"):
        entity = ds.entity
        category = entity.category if entity else None
        subsector = category.subsector if category else None
        sector = subsector.sector if subsector else None
        if not (entity and category and subsector and sector):
            continue

        sector_node = grouped.setdefault(
            sector.id,
            {"id": sector.id, "name": sector.name, "subsectors": {}},
        )
        subsector_node = sector_node["subsectors"].setdefault(
            subsector.id,
            {"id": subsector.id, "name": subsector.name, "categories": {}},
        )
        category_node = subsector_node["categories"].setdefault(
            category.id,
            {"id": category.id, "name": category.name, "entities": {}},
        )
        entity_node = category_node["entities"].setdefault(
            entity.id,
            {"id": entity.id, "name": entity.name, "code": entity.code, "datasets": []},
        )
        entity_node["datasets"].append(ds)

    result = []
    for sector_node in grouped.values():
        subsectors = []
        for subsector_node in sector_node["subsectors"].values():
            categories = []
            for category_node in subsector_node["categories"].values():
                entities = list(category_node["entities"].values())
                entities.sort(key=lambda e: (e["name"] or "").lower())
                for entity_node in entities:
                    entity_node["datasets"].sort(key=lambda d: (d.name or "").lower())
                categories.append(
                    {
                        "id": category_node["id"],
                        "name": category_node["name"],
                        "entities": entities,
                    }
                )
            categories.sort(key=lambda c: (c["name"] or "").lower())
            subsectors.append(
                {
                    "id": subsector_node["id"],
                    "name": subsector_node["name"],
                    "categories": categories,
                }
            )
        subsectors.sort(key=lambda s: (s["name"] or "").lower())
        result.append({"id": sector_node["id"], "name": sector_node["name"], "subsectors": subsectors})
    result.sort(key=lambda s: (s["name"] or "").lower())
    return result


@login_required
def charts(request):
    user = request.user
    is_admin, is_loader, is_validator, is_viewer = _get_role_flags(user)
    viewer_profile_type = _get_viewer_profile_type(user)
    is_external_monthly_viewer = (
        is_viewer
        and viewer_profile_type == AccountProfile.VIEWER_EXTERNAL_MONTHLY
        and not is_admin
        and not is_loader
        and not is_validator
    )
    is_authority_mhe_viewer = (
        is_viewer
        and viewer_profile_type == AccountProfile.VIEWER_AUTHORITY_MHE
        and not is_admin
        and not is_loader
        and not is_validator
    )

    datasets = DatasetType.objects.select_related("entity")
    datasets = _apply_membership_scope(user, is_admin, datasets)
    if is_external_monthly_viewer:
        datasets = datasets.filter(validation_frequency=DatasetType.MONTHLY)

    sector_id = request.GET.get("sector")
    subsector_id = request.GET.get("subsector")
    category_id = request.GET.get("category")
    entity_id = request.GET.get("entity")
    if sector_id:
        datasets = datasets.filter(entity__category__subsector__sector_id=sector_id)
    if subsector_id:
        datasets = datasets.filter(entity__category__subsector_id=subsector_id)
    if category_id:
        datasets = datasets.filter(entity__category_id=category_id)
    if entity_id:
        datasets = datasets.filter(entity_id=entity_id)

    datasets = (
        datasets.filter(instances__isnull=False)
        .distinct()
        .order_by("entity__name", "name", "-version")
    )

    can_see_drafts = (is_admin or is_loader or is_validator) and not is_viewer

    performance_indicators = PerformanceIndicator.objects.none()
    if is_admin:
        performance_indicators = (
            PerformanceIndicator.objects.select_related("plant")
            .filter(is_active=True, results__isnull=False)
            .distinct()
            .order_by("plant__code", "label", "key")
        )

    template_name = "kpis/charts.html"
    if is_external_monthly_viewer:
        template_name = "kpis/charts_external.html"
    elif is_authority_mhe_viewer:
        template_name = "kpis/charts_authority.html"

    return render(
        request,
        template_name,
        {
            "datasets": datasets,
            "can_see_drafts": can_see_drafts,
            "performance_indicators": performance_indicators,
            "is_external_monthly_viewer": is_external_monthly_viewer,
            "is_authority_mhe_viewer": is_authority_mhe_viewer,
            "viewer_profile_type": viewer_profile_type,
            "authority_dataset_tree": _group_datasets_for_authority(datasets),
            "selected_sector": sector_id or "",
            "selected_subsector": subsector_id or "",
            "selected_category": category_id or "",
            "selected_entity": entity_id or "",
        },
    )


@login_required
def dataset_data(request, dataset_id: int):
    user = request.user
    is_admin, is_loader, is_validator, is_viewer = _get_role_flags(user)
    viewer_profile_type = _get_viewer_profile_type(user)
    is_external_monthly_viewer = (
        is_viewer
        and viewer_profile_type == AccountProfile.VIEWER_EXTERNAL_MONTHLY
        and not is_admin
        and not is_loader
        and not is_validator
    )

    dataset = get_object_or_404(
        DatasetType.objects.select_related("entity"),
        pk=dataset_id,
    )

    if not is_admin:
        memberships = Membership.objects.filter(user=user, is_active=True)
        entity_ids = list(memberships.exclude(entity__isnull=True).values_list("entity_id", flat=True))
        has_global = memberships.filter(entity__isnull=True).exists()
        if not (has_global or (entity_ids and dataset.entity_id in entity_ids)):
            raise Http404

    if is_external_monthly_viewer and dataset.validation_frequency != DatasetType.MONTHLY:
        raise Http404

    can_see_drafts = (is_admin or is_loader or is_validator) and not is_viewer
    source = (request.GET.get("source") or "published").lower()
    if source not in ("published", "draft"):
        source = "published"
    include_drafts = source == "draft"

    if include_drafts and not can_see_drafts:
        raise Http404
    if source == "published" and not (is_admin or is_loader or is_validator or is_viewer):
        raise Http404

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
    columns_map = {col.name: col for col in columns_qs}

    def _normalize_date_value(raw_value):
        if raw_value in (None, ""):
            return raw_value
        if isinstance(raw_value, datetime):
            return raw_value.date().isoformat()
        if isinstance(raw_value, date):
            return raw_value.isoformat()
        text = str(raw_value).strip()
        if not text:
            return ""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        try:
            parsed_date = date.fromisoformat(text)
            return parsed_date.isoformat()
        except ValueError:
            pass
        try:
            parsed_dt = datetime.fromisoformat(text)
            return parsed_dt.date().isoformat()
        except ValueError:
            return text

    published_states = [DatasetInstance.STATE_PUBLISHED, DatasetInstance.STATE_LOCKED]
    published_points = (
        PublishedDataPoint.objects.filter(
            instance__dataset_type=dataset,
            instance__state__in=published_states,
        )
        .select_related("column", "instance")
        .order_by(
            "instance__period",
            "instance_id",
            "row_index",
            "column__display_order",
            "column__name",
        )
    )

    rows = []
    current_key = None
    current_row = None

    def _append_current_row():
        nonlocal current_row
        if current_row:
            rows.append(current_row)
            current_row = None

    for point in published_points:
        key = (point.instance_id, point.row_index)
        if key != current_key:
            _append_current_row()
            current_key = key
            current_row = {
                "row_index": 0,
                "values": {},
                "period": point.instance.period.isoformat(),
                "source": "published",
                "_sort_key": (point.instance.period, 0, point.row_index),
            }

        if point.numeric_value is not None:
            value = point.numeric_value
        elif point.date_value is not None:
            value = point.date_value.isoformat()
        elif point.bool_value is not None:
            value = bool(point.bool_value)
        else:
            if point.column.data_type == "DATE":
                value = _normalize_date_value(point.text_value)
            else:
                value = point.text_value
        current_row["values"][point.column.name] = value

    _append_current_row()

    def _build_header_map():
        header_map = {}
        for col in columns_qs:
            key = (col.label or col.name or "").strip().lower()
            if key:
                header_map[key] = col.name
        return header_map

    if include_drafts:
        draft_instance = (
            DatasetInstance.objects.filter(dataset_type=dataset)
            .exclude(state__in=published_states)
            .order_by("-period", "-created_at")
            .first()
        )

        if draft_instance:
            header, parsed_rows = _read_instance_file(draft_instance)
            header_map = _build_header_map()
            name_by_index = [
                header_map.get((name or "").strip().lower()) for name in header
            ]

            for parsed in parsed_rows:
                values = {}
                for idx, raw in enumerate(parsed.values):
                    col_name = name_by_index[idx] if idx < len(name_by_index) else None
                    if not col_name:
                        continue
                    col_def = columns_map.get(col_name)
                    if col_def and col_def.data_type == "DATE":
                        values[col_name] = _normalize_date_value(raw)
                    else:
                        values[col_name] = raw

                rows.append(
                    {
                        "row_index": 0,
                        "values": values,
                        "period": draft_instance.period.isoformat(),
                        "source": "draft",
                        "_sort_key": (draft_instance.period, 1, parsed.row_index),
                    }
                )

    rows.sort(key=lambda r: r["_sort_key"])
    for idx, row in enumerate(rows, start=1):
        row["row_index"] = idx
        row.pop("_sort_key", None)

    data = {
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "entity_code": dataset.entity.code,
            "entity_name": dataset.entity.name,
            # Compatibilidad temporal para JS legado.
            "plant_code": dataset.entity.code,
            "plant_name": dataset.entity.name,
            "validation_frequency": dataset.validation_frequency,
            "is_certification": dataset.is_certification,
        },
        "columns": columns,
        "rows": rows,
    }

    return JsonResponse(data)


@login_required
def performance_data(request, indicator_id: int):
    user = request.user
    is_admin, is_loader, is_validator, is_viewer = _get_role_flags(user)

    if not is_admin:
        raise Http404

    indicator = get_object_or_404(PerformanceIndicator.objects.select_related("plant"), pk=indicator_id)

    if not (is_admin or is_loader or is_validator or is_viewer):
        raise Http404

    frequency = (request.GET.get("frequency") or PerformanceIndicatorResult.FREQ_MONTHLY).upper()
    if frequency not in (
        PerformanceIndicatorResult.FREQ_DAILY,
        PerformanceIndicatorResult.FREQ_MONTHLY,
    ):
        frequency = PerformanceIndicatorResult.FREQ_MONTHLY

    def _parse_date(raw):
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    start_date = _parse_date(request.GET.get("date_start"))
    end_date = _parse_date(request.GET.get("date_end"))
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    qs = (
        PerformanceIndicatorResult.objects.filter(
            indicator=indicator,
            plant=indicator.plant,
            frequency=frequency,
        )
        .order_by("period_end")
    )
    if start_date:
        qs = qs.filter(period_end__gte=start_date)
    if end_date:
        qs = qs.filter(period_end__lte=end_date)

    rows = []
    for res in qs:
        rows.append(
            {
                "period_end": res.period_end.isoformat(),
                "value": res.numeric_value if res.status == PerformanceIndicatorResult.STATUS_SUCCESS else None,
                "status": res.status,
            }
        )

    data = {
        "indicator": {
            "id": indicator.id,
            "key": indicator.key,
            "label": indicator.label,
            "unit": indicator.unit,
            "plant_code": indicator.plant.code,
            "plant_name": indicator.plant.name,
        },
        "frequency": frequency,
        "rows": rows,
    }

    return JsonResponse(data)
