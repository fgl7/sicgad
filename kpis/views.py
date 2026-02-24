import logging
from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q, Exists, OuterRef
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import AccountProfile, Institution, Membership
from audit.models import AuditLog
from ingest.models import DatasetInstance, PublishedDataPoint
from performance.models import PerformanceIndicator, PerformanceIndicatorResult
from ingest.utils import _read_instance_file
from schemas.models import DatasetType
from schemas.services import ensure_previous_month_consolidated


logger = logging.getLogger(__name__)


def _build_landing_stats():
    cached = cache.get("kpis:landing:stats:v1")
    if cached:
        return cached

    published_states = [DatasetInstance.STATE_PUBLISHED, DatasetInstance.STATE_LOCKED]
    published_instances = DatasetInstance.objects.filter(state__in=published_states)

    published_total = published_instances.count()
    published_datasets = (
        published_instances.values("dataset_type_id").distinct().count()
    )
    published_entities = (
        published_instances.values("entity_id").distinct().count()
    )
    published_sectors = (
        published_instances
        .values("entity__category__subsector__sector_id")
        .distinct()
        .count()
    )
    published_subsectors = (
        published_instances
        .values("entity__category__subsector_id")
        .distinct()
        .count()
    )

    latest_instance = (
        published_instances.select_related("dataset_type", "entity")
        .order_by("-period", "-created_at")
        .first()
    )

    institutions_total = Institution.objects.count()
    institutions_active = Institution.objects.filter(is_active=True).count()

    stats = {
        "published_total": published_total,
        "published_datasets": published_datasets,
        "published_entities": published_entities,
        "published_sectors": published_sectors,
        "published_subsectors": published_subsectors,
        "latest_period": latest_instance.period if latest_instance else None,
        "latest_dataset_name": latest_instance.dataset_type.name if latest_instance else "",
        "latest_entity_name": latest_instance.entity.name if latest_instance else "",
        "institutions_total": institutions_total,
        "institutions_active": institutions_active,
    }

    cache.set("kpis:landing:stats:v1", stats, timeout=120)
    return stats

def landing(request):
    return render(
        request,
        "landing.html",
        {
            "landing_stats": _build_landing_stats(),
        },
    )


@login_required
def home(request):
    user = request.user
    is_admin, is_loader, is_validator, is_viewer = _get_role_flags(user)

    # Los visualizadores puros no usan el dashboard de inicio; entran directo a KPIs.
    if is_viewer and not is_admin and not is_loader and not is_validator:
        return redirect("kpis_charts")

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

    if is_external_monthly_viewer:
        try:
            ensure_previous_month_consolidated()
        except Exception:
            logger.exception(
                "Error ejecutando consolidacion mensual automatica para visualizador externo."
            )

    datasets = DatasetType.objects.select_related("entity")
    datasets = _apply_membership_scope(user, is_admin, datasets)
    if is_external_monthly_viewer:
        datasets = datasets.filter(validation_frequency=DatasetType.MONTHLY)
    authority_tree_datasets = datasets

    sector_id = request.GET.get("sector")
    subsector_id = request.GET.get("subsector")
    category_id = request.GET.get("category")
    entity_id = request.GET.get("entity")

    # Para visualizador externo mensual, forzamos seleccion jerarquica inicial
    # completa (sector/subsector/categoria) para que el selector de datasets
    # se alimente desde el sidebar con un alcance concreto desde el primer ingreso.
    has_hierarchy_filter = any([sector_id, subsector_id, category_id, entity_id])
    if is_external_monthly_viewer and not has_hierarchy_filter:
        first_path = (
            authority_tree_datasets
            .filter(instances__isnull=False)
            .exclude(entity__category__subsector__sector_id__isnull=True)
            .exclude(entity__category__subsector_id__isnull=True)
            .exclude(entity__category_id__isnull=True)
            .order_by(
                "entity__category__subsector__sector__name",
                "entity__category__subsector__name",
                "entity__category__name",
            )
            .values_list(
                "entity__category__subsector__sector_id",
                "entity__category__subsector_id",
                "entity__category_id",
            )
            .first()
        )
        if first_path:
            first_sector_id, first_subsector_id, first_category_id = first_path
            query = request.GET.copy()
            query["sector"] = str(first_sector_id)
            query["subsector"] = str(first_subsector_id)
            query["category"] = str(first_category_id)
            return redirect(f"{request.path}?{query.urlencode()}")

    if sector_id:
        datasets = datasets.filter(entity__category__subsector__sector_id=sector_id)
    if subsector_id:
        datasets = datasets.filter(entity__category__subsector_id=subsector_id)
    if category_id:
        datasets = datasets.filter(entity__category_id=category_id)
    if entity_id:
        datasets = datasets.filter(entity_id=entity_id)

    has_instances_subquery = DatasetInstance.objects.filter(dataset_type_id=OuterRef("pk"))
    datasets = (
        datasets.annotate(_has_instances=Exists(has_instances_subquery))
        .filter(_has_instances=True)
        .order_by("entity__name", "name", "-version")
    )
    authority_tree_datasets = (
        authority_tree_datasets.annotate(_has_instances=Exists(has_instances_subquery))
        .filter(_has_instances=True)
        .order_by("entity__name", "name", "-version")
    )

    can_see_drafts = (is_admin or is_loader or is_validator) and not is_viewer

    performance_indicators = PerformanceIndicator.objects.none()
    if is_admin:
        performance_indicators = (
            PerformanceIndicator.objects.select_related("entity")
            .filter(is_active=True, results__isnull=False)
            .distinct()
            .order_by("entity__code", "label", "key")
        )

    template_name = "kpis/charts.html"
    if is_external_monthly_viewer:
        template_name = "kpis/charts_external.html"
    elif is_authority_mhe_viewer:
        template_name = "kpis/charts_authority.html"

    authority_dataset_tree = []
    if is_external_monthly_viewer or is_authority_mhe_viewer:
        authority_dataset_tree = _group_datasets_for_authority(authority_tree_datasets)

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
            "authority_dataset_tree": authority_dataset_tree,
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

    cache_key = None
    if source == "published":
        cache_key = f"kpis:dataset-data:published:v2:{dataset.id}"
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return JsonResponse(cached_payload)

    columns_list = list(
        dataset.columns.filter(is_active=True).order_by("display_order", "name")
    )
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
        for col in columns_list
    ]
    columns_map = {col.name: col for col in columns_list}

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
        .order_by(
            "instance__period",
            "instance_id",
            "row_index",
            "column__display_order",
            "column__name",
        )
        .values_list(
            "instance_id",
            "row_index",
            "instance__period",
            "column__name",
            "column__data_type",
            "numeric_value",
            "date_value",
            "bool_value",
            "text_value",
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

    for (
        point_instance_id,
        point_row_index,
        point_period,
        point_column_name,
        point_column_data_type,
        point_numeric_value,
        point_date_value,
        point_bool_value,
        point_text_value,
    ) in published_points.iterator(chunk_size=2000):
        key = (point_instance_id, point_row_index)
        if key != current_key:
            _append_current_row()
            current_key = key
            current_row = {
                "values": {},
                "period": point_period.isoformat(),
                "source": "published",
                "_sort_key": (point_period, 0, point_row_index),
            }

        if point_numeric_value is not None:
            value = point_numeric_value
        elif point_date_value is not None:
            value = point_date_value.isoformat()
        elif point_bool_value is not None:
            value = bool(point_bool_value)
        else:
            if point_column_data_type == "DATE":
                value = _normalize_date_value(point_text_value)
            else:
                value = point_text_value
        current_row["values"][point_column_name] = value

    _append_current_row()

    def _build_header_map():
        header_map = {}
        for col in columns_list:
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
                        "values": values,
                        "period": draft_instance.period.isoformat(),
                        "source": "draft",
                        "_sort_key": (draft_instance.period, 1, parsed.row_index),
                    }
                )

    rows.sort(key=lambda r: r["_sort_key"])
    for row in rows:
        row.pop("_sort_key", None)

    data = {
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "entity_code": dataset.entity.code,
            "entity_name": dataset.entity.name,
            "validation_frequency": dataset.validation_frequency,
            "is_certification": dataset.is_certification,
        },
        "columns": columns,
        "rows": rows,
    }

    if cache_key:
        cache.set(cache_key, data, timeout=180)

    return JsonResponse(data)


@login_required
def performance_data(request, indicator_id: int):
    user = request.user
    is_admin, is_loader, is_validator, is_viewer = _get_role_flags(user)

    if not is_admin:
        raise Http404

    indicator = get_object_or_404(PerformanceIndicator.objects.select_related("entity"), pk=indicator_id)

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
            entity=indicator.entity,
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
            "entity_code": indicator.entity.code,
            "entity_name": indicator.entity.name,
        },
        "frequency": frequency,
        "rows": rows,
    }

    return JsonResponse(data)
