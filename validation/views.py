import calendar
import logging
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q, F, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.cache_utils import invalidate_admin_flags_cache
from accounts.models import Membership
from ingest.file_cleanup import cleanup_files_after_publication
from ingest.models import DatasetInstance, PublishedDataPoint, HistoricalImportBatch
from ingest.utils import materialize_instance
from schemas.models import DatasetType
from schemas.services import (
    collect_certification_status,
    consolidate_certifications_for_daily_periods,
    previous_month_range,
)

from audit.utils import record_action
from .forms import ValidationDecisionForm
from .models import ValidationAction
from .services import determine_periodic_state

from django.db.models import Count, Min, Max


PUBLISHED_STATES = [
    DatasetInstance.STATE_PUBLISHED,
    DatasetInstance.STATE_LOCKED,
]
logger = logging.getLogger(__name__)


def _is_ajax_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _json_or_redirect(request, url_name, **kwargs):
    url = reverse(url_name, kwargs=kwargs) if kwargs else reverse(url_name)
    if _is_ajax_request(request):
        return JsonResponse({"ok": True, "redirect_url": url})
    return redirect(url)


def _historical_approve_progress_key(user_id: int, batch_id: int) -> str:
    return f"validation:historical-approve-progress:v1:u{user_id}:b{batch_id}"


def _set_historical_approve_progress(
    *,
    user_id: int,
    batch_id: int,
    status: str,
    percent: int,
    message: str,
    error: str = "",
    redirect_url: str = "",
    stage_index: int | None = None,
    stage_total: int | None = None,
    stage_label: str = "",
    timeout: int = 900,
):
    payload = {
        "status": status,
        "percent": max(0, min(100, int(percent))),
        "message": message or "",
        "error": error or "",
        "redirect_url": redirect_url or "",
        "stage_index": stage_index,
        "stage_total": stage_total,
        "stage_label": stage_label or "",
    }
    cache.set(_historical_approve_progress_key(user_id, batch_id), payload, timeout=timeout)
    return payload


def _get_historical_approve_progress(user_id: int, batch_id: int):
    return cache.get(_historical_approve_progress_key(user_id, batch_id))


def _format_value_for_display(column, value):
    if value in (None, ""):
        return "-"
    if column.data_type == "DATE":
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        return str(value)
    if column.data_type == "BOOLEAN":
        return "Si" if bool(value) else "No"
    return str(value)


def _coerce_to_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            pass
        if " " in text:
            head = text.split(" ", 1)[0]
            try:
                return datetime.fromisoformat(head).date()
            except ValueError:
                pass
    return None


def _build_rows_from_points(instance_obj):
    points = (
        PublishedDataPoint.objects.filter(instance=instance_obj)
        .select_related("column")
        .order_by("row_index", "column__display_order", "column__name")
    )
    rows_map: dict[int, dict] = {}
    for point in points:
        row = rows_map.setdefault(point.row_index, {})
        if point.numeric_value is not None:
            value = point.numeric_value
        elif point.date_value is not None:
            value = point.date_value
        elif point.bool_value is not None:
            value = bool(point.bool_value)
        else:
            value = point.text_value
        row[point.column.name] = value
    return rows_map


def _build_monthly_review_context(instance: DatasetInstance):
    dataset = instance.dataset_type
    source = dataset.source_dataset
    if not source:
        return None

    monthly_columns = list(
        dataset.columns.filter(is_active=True).order_by("display_order", "name")
    )
    monthly_values_map = {}
    for point in PublishedDataPoint.objects.filter(instance=instance).select_related("column"):
        col = point.column
        if col.data_type in ("INTEGER", "FLOAT"):
            value = point.numeric_value
        elif col.data_type == "DATE":
            value = point.date_value
        elif col.data_type == "BOOLEAN":
            value = point.bool_value
        else:
            value = point.text_value
        monthly_values_map[col.name] = value

    monthly_value_rows = [
        {
            "column": column,
            "value": _format_value_for_display(column, monthly_values_map.get(column.name)),
        }
        for column in monthly_columns
    ]

    source_columns = list(
        source.columns.filter(is_active=True).order_by("display_order", "name")
    )
    display_columns = [col for col in source_columns if col.data_type != "DATE"]
    if not display_columns:
        display_columns = list(source_columns)

    month_start = instance.period.replace(day=1)
    last_day = calendar.monthrange(instance.period.year, instance.period.month)[1]
    month_end = instance.period.replace(day=last_day)
    month_dates = [date(instance.period.year, instance.period.month, day) for day in range(1, last_day + 1)]

    monthly_instances = list(
        DatasetInstance.objects.filter(
            dataset_type=source,
            entity=instance.entity,
            state__in=PUBLISHED_STATES,
            period__gte=month_start,
            period__lte=month_end,
        ).order_by("period", "created_at")
    )
    if not monthly_instances:
        return None

    rows_cache = {inst.id: _build_rows_from_points(inst) for inst in monthly_instances}
    date_column = next((col for col in source_columns if col.data_type == "DATE"), None)
    date_entries: dict[date, dict] = {}
    for daily_instance in monthly_instances:
        cached_rows = rows_cache.get(daily_instance.id, {})
        for row_index, row_values in cached_rows.items():
            raw_date = row_values.get(date_column.name) if date_column else daily_instance.period
            parsed_date = _coerce_to_date(raw_date)
            if not parsed_date:
                continue
            if parsed_date < month_start or parsed_date > month_end:
                continue
            current = date_entries.get(parsed_date)
            should_replace = False
            if current is None:
                should_replace = True
            else:
                current_created = current["instance"].created_at
                if daily_instance.created_at > current_created:
                    should_replace = True
                elif daily_instance.id == current["instance"].id and row_index > current["row_index"]:
                    should_replace = True
            if should_replace:
                date_entries[parsed_date] = {
                    "instance": daily_instance,
                    "row_index": row_index,
                    "values": row_values,
                }

    changed_dates = set(
        instance.change_requests.filter(target_period__isnull=False).values_list("target_period", flat=True)
    )

    daily_rows = []
    for target_date in month_dates:
        entry = date_entries.get(target_date)
        if entry:
            values = [
                {
                    "column": column,
                    "display": _format_value_for_display(column, entry["values"].get(column.name)),
                }
                for column in display_columns
            ]
            daily_rows.append(
                {
                    "date": target_date,
                    "values": values,
                    "changed": target_date in changed_dates,
                    "has_instance": True,
                }
            )
        else:
            values = [
                {
                    "column": column,
                    "display": "-",
                }
                for column in display_columns
            ]
            daily_rows.append(
                {
                    "date": target_date,
                    "values": values,
                    "changed": target_date in changed_dates,
                    "has_instance": False,
                }
            )

    return {
        "daily_rows": daily_rows,
        "daily_display_columns": display_columns,
        "monthly_values": monthly_value_rows,
        "monthly_columns": monthly_columns,
    }


@login_required
def inbox(request):
    """
    Bandeja de validacion para validadores.
    Los administradores usarÃ¡n una vista de resumen separada.
    """
    user = request.user

    if user.is_superuser or Membership.objects.filter(
        user=user, role="ADMIN", is_active=True
    ).exists():
        return redirect("validation:admin_overview")

    # Si el usuario no es validador, lo redirigimos al historial de cargas,
    # donde podrÃ¡ ver el estado y comentarios de sus datasets.
    is_validator = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
    ).exists()
    if not is_validator:
        messages.info(
            request,
            "La bandeja de validaciÃ³n estÃ¡ disponible solo para validadores. "
            "Puedes revisar el estado y comentarios de tus cargas en el historial.",
        )
        return redirect("ingest:upload_history")

    daily_memberships = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_daily=True,
    )
    weekly_memberships = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_weekly=True,
    )
    projections_memberships = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_projections=True,
    )
    monthly_memberships = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_monthly=True,
    )

    daily_entities = [m.entity_id for m in daily_memberships if m.entity_id]
    weekly_entities = [m.entity_id for m in weekly_memberships if m.entity_id]
    projections_entities = [m.entity_id for m in projections_memberships if m.entity_id]
    monthly_entities = [m.entity_id for m in monthly_memberships if m.entity_id]

    has_global_daily = any(m.entity_id is None for m in daily_memberships)
    has_global_weekly = any(m.entity_id is None for m in weekly_memberships)
    has_global_projections = any(
        m.entity_id is None for m in projections_memberships
    )
    has_global_monthly = any(
        m.entity_id is None for m in monthly_memberships
    )

    base_qs = DatasetInstance.objects.select_related("dataset_type", "entity").filter(
        state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1]
    )

    daily_filter = Q(dataset_type__validation_frequency=DatasetType.DAILY)
    if not has_global_daily:
        if daily_entities:
            daily_filter &= Q(entity_id__in=daily_entities)
        else:
            daily_filter = Q(pk__in=[])

    weekly_filter = Q(dataset_type__validation_frequency=DatasetType.WEEKLY)
    if not has_global_weekly:
        if weekly_entities:
            weekly_filter &= Q(entity_id__in=weekly_entities)
        else:
            weekly_filter = Q(pk__in=[])

    projections_filter = Q(dataset_type__validation_frequency=DatasetType.FLEXIBLE)
    if not has_global_projections:
        if projections_entities:
            projections_filter &= Q(entity_id__in=projections_entities)
        else:
            projections_filter = Q(pk__in=[])

    monthly_filter = Q(dataset_type__validation_frequency=DatasetType.MONTHLY)
    if not has_global_monthly:
        if monthly_entities:
            monthly_filter &= Q(entity_id__in=monthly_entities)
        else:
            monthly_filter = Q(pk__in=[])

    approval_subquery = ValidationAction.objects.filter(
        dataset_instance=OuterRef("pk"),
        user=user,
        decision=ValidationAction.DECISION_APPROVE,
    )
    approval_since_submit = approval_subquery.filter(created_at__gte=OuterRef("submitted_at"))

    items = (
        base_qs.filter(daily_filter | weekly_filter | projections_filter | monthly_filter)
        .order_by("-created_at")
        .annotate(
            already_approved_history=Exists(approval_subquery),
            already_approved_recent=Exists(approval_since_submit),
        )
        .filter(
            Q(submitted_at__isnull=True, already_approved_history=False)
            | Q(submitted_at__isnull=False, already_approved_recent=False)
        )
    )

    # Historial de validaciones realizadas por este usuario (como validador)
    history_actions = (
        ValidationAction.objects.select_related(
            "dataset_instance",
            "dataset_instance__dataset_type",
            "dataset_instance__entity",
            "dataset_instance__entity",
        )
        .filter(validator__user=user, validator__is_active=True)
        .order_by("-created_at")[:50]
    )

    certification_alerts = []
    if monthly_memberships.exists():
        _, previous_month_end = previous_month_range()
        pending_cert_states = [
            DatasetInstance.STATE_SUBMITTED,
            DatasetInstance.STATE_VALIDATED_L1,
            DatasetInstance.STATE_VALIDATED_L2,
            DatasetInstance.STATE_LOCKED,
        ]
        cert_qs = (
            DatasetInstance.objects.select_related("dataset_type", "entity")
            .filter(
                dataset_type__validation_frequency=DatasetType.MONTHLY,
                dataset_type__is_certification=True,
                period=previous_month_end,
                state__in=pending_cert_states,
            )
            .order_by("entity__name", "dataset_type__name")
        )
        if not has_global_monthly:
            if monthly_entities:
                cert_qs = cert_qs.filter(entity_id__in=monthly_entities)
            else:
                cert_qs = cert_qs.none()

        cert_qs = cert_qs.annotate(
            already_approved_history=Exists(approval_subquery),
            already_approved_recent=Exists(approval_since_submit),
        ).filter(
            Q(submitted_at__isnull=True, already_approved_history=False)
            | Q(submitted_at__isnull=False, already_approved_recent=False)
        )
        certification_alerts = list(cert_qs)

    profile = getattr(request.user, "profile", None)
    if profile and certification_alerts:
        profile.last_seen_certification_alert = timezone.now()
        profile.save(update_fields=["last_seen_certification_alert"])
        invalidate_admin_flags_cache(request.user.id)

    pending_historical_batches = []
    if daily_memberships.exists():
        batch_qs = HistoricalImportBatch.objects.select_related("dataset_type", "entity").filter(
            dataset_type__validation_frequency=DatasetType.DAILY,
            instances__state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1],
        )
        if not has_global_daily:
            if daily_entities:
                batch_qs = batch_qs.filter(entity_id__in=daily_entities)
            else:
                batch_qs = batch_qs.none()

        batch_qs = (
            batch_qs.distinct()
            .annotate(
                pending_count=Count(
                    "instances",
                    filter=Q(
                        instances__state__in=[
                            DatasetInstance.STATE_SUBMITTED,
                            DatasetInstance.STATE_VALIDATED_L1,
                        ]
                    ),
                ),
                inst_period_start=Min("instances__period"),
                inst_period_end=Max("instances__period"),
            )
            .order_by("-created_at")[:20]
        )
        pending_historical_batches = list(batch_qs)

    return render(
        request,
        "validate/inbox.html",
        {
            "items": items,
            "history_actions": history_actions,
            "certification_alerts": certification_alerts,
            "pending_historical_batches": pending_historical_batches,
        },
    )


@login_required
def approve_historical_batch(request, batch_id: int):
    if request.method != "POST":
        return _json_or_redirect(request, "validation:inbox")

    batch = get_object_or_404(
        HistoricalImportBatch.objects.select_related("dataset_type", "entity"),
        pk=batch_id,
    )
    if batch.dataset_type.validation_frequency != DatasetType.DAILY:
        return _json_or_redirect(request, "validation:inbox")

    user = request.user
    base_qs = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_daily=True,
    )
    membership = base_qs.filter(entity=batch.entity).order_by("validation_level").first()
    if not membership:
        membership = base_qs.filter(entity__isnull=True).order_by("validation_level").first()


    if not membership:
        messages.error(request, "No tiene permisos de validaciÃ³n diaria para este histÃ³rico.")
        return _json_or_redirect(request, "validation:inbox")

    approval_subquery = ValidationAction.objects.filter(
        dataset_instance=OuterRef("pk"),
        user=user,
        decision=ValidationAction.DECISION_APPROVE,
    )
    approval_since_submit = approval_subquery.filter(created_at__gte=OuterRef("submitted_at"))

    target_qs = (
        DatasetInstance.objects.filter(
            historical_batch=batch,
            state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1],
        )
        .annotate(
            already_approved_recent=Exists(approval_since_submit),
        )
        .filter(
            Q(submitted_at__isnull=True, already_approved_recent=False)
            | Q(submitted_at__isnull=False, already_approved_recent=False)
        )
    )

    approved_periods = list(target_qs.values_list("period", flat=True).distinct())
    instance_ids = list(target_qs.values_list("id", flat=True))
    rematerialize_ids = list(
        DatasetInstance.objects.filter(
            historical_batch=batch,
            state__in=[DatasetInstance.STATE_PUBLISHED, DatasetInstance.STATE_LOCKED],
        )
        .annotate(points_count=Count("published_points"))
        .filter(points_count=0)
        .values_list("id", flat=True)
    )
    if not instance_ids and not rematerialize_ids:
        messages.info(request, "No hay instancias pendientes para aprobar en este histÃ³rico.")
        _set_historical_approve_progress(
            user_id=user.id,
            batch_id=batch.id,
            status="DONE",
            percent=100,
            message="No hay instancias pendientes para aprobar.",
            redirect_url=reverse("validation:inbox"),
            stage_index=4,
            stage_total=4,
            stage_label="Completado",
            timeout=300,
        )
        return _json_or_redirect(request, "validation:inbox")

    total_materialize = len(dict.fromkeys(instance_ids + rematerialize_ids))
    progress_total_units = max(1, total_materialize) + 5
    progress_done_units = 0

    def push_progress(
        message,
        *,
        status="RUNNING",
        error="",
        percent_override=None,
        stage_index=None,
        stage_total=4,
        stage_label="",
        timeout=900,
    ):
        nonlocal progress_done_units
        if percent_override is None:
            percent = max(1, min(99, int((progress_done_units * 100) / progress_total_units)))
        else:
            percent = percent_override
        _set_historical_approve_progress(
            user_id=user.id,
            batch_id=batch.id,
            status=status,
            percent=percent,
            message=message,
            error=error,
            redirect_url=reverse("validation:inbox") if status == "DONE" else "",
            stage_index=stage_index,
            stage_total=stage_total,
            stage_label=stage_label,
            timeout=timeout,
        )

    push_progress(
        "Preparando aprobacion del historico...",
        percent_override=1,
        stage_index=1,
        stage_label="Preparacion",
    )

    level = membership.validation_level if membership.validation_level else 1
    now = timezone.now()

    if instance_ids:
        actions = [
            ValidationAction(
                dataset_instance_id=instance_id,
                validator=membership,
                user=user,
                level=level,
                decision=ValidationAction.DECISION_APPROVE,
                comment="AprobaciÃ³n masiva de histÃ³rico.",
            )
            for instance_id in instance_ids
        ]
        ValidationAction.objects.bulk_create(actions, batch_size=1000)

        DatasetInstance.objects.filter(id__in=instance_ids).update(
            state=DatasetInstance.STATE_PUBLISHED,
            updated_at=now,
        )

    progress_done_units += 1
    push_progress(
        "Instancias aprobadas. Preparando materializacion...",
        stage_index=2,
        stage_label="Materializacion",
    )

    materialize_ids = list(dict.fromkeys(instance_ids + rematerialize_ids))
    materialized_ok = 0
    materialize_errors = 0
    materialized_instance_ids: list[int] = []
    if materialize_ids:
        push_progress(
            f"Materializando datos publicados... (0/{len(materialize_ids)} instancias)",
            stage_index=2,
            stage_label="Materializacion",
        )
        # ContinÃºa aunque una instancia puntual falle para evitar dejar el lote a medias.
        for idx, instance in enumerate(
            DatasetInstance.objects.filter(id__in=materialize_ids)
            .select_related("dataset_type")
            .iterator(chunk_size=50),
            start=1,
        ):
            try:
                materialize_instance(instance)
                materialized_ok += 1
                materialized_instance_ids.append(instance.id)
            except Exception:
                materialize_errors += 1
            progress_done_units += 1
            if idx == len(materialize_ids) or idx % 5 == 0:
                push_progress(
                    f"Materializando datos publicados... ({idx}/{len(materialize_ids)} instancias)",
                    stage_index=2,
                    stage_label="Materializacion",
                )

    else:
        progress_done_units += 1
        push_progress(
            "No se requiere materializacion adicional.",
            stage_index=2,
            stage_label="Materializacion",
        )

    cleaned_files_count = 0
    if materialized_instance_ids:
        try:
            cleanup_result = cleanup_files_after_publication(
                instance_ids=set(materialized_instance_ids),
                batch_ids={batch.id},
                apply_changes=True,
            )
            cleaned_files_count = cleanup_result.total_count
        except Exception:
            logger.exception(
                "Error limpiando archivos tras aprobar historico (batch=%s).",
                batch.id,
            )

    progress_done_units += 1
    push_progress(
        "Limpieza de archivos completada. Consolidando certificaciones...",
        stage_index=3,
        stage_label="Consolidacion",
    )

    if instance_ids:
        messages.success(request, f"HistÃ³rico aprobado: {len(instance_ids)} dÃ­as.")
    if rematerialize_ids:
        messages.info(
            request,
            f"Se reprocesaron {materialized_ok} instancias publicadas sin puntos materializados.",
        )
    if materialize_errors:
        messages.warning(
            request,
            f"No se pudieron materializar {materialize_errors} instancias. Revise el lote.",
        )
    consolidated_count = 0
    if approved_periods:
        try:
            consolidated = consolidate_certifications_for_daily_periods(
                batch.dataset_type,
                batch.entity,
                approved_periods,
                request=request,
            )
            consolidated_count = len(consolidated)
        except Exception:
            logger.exception(
                "Error consolidando certificaciones tras aprobar historico (batch=%s).",
                batch.id,
            )
            messages.warning(
                request,
                "El historico se aprobo, pero fallo la consolidacion mensual automatica.",
            )
        else:
            if consolidated_count:
                messages.info(
                    request,
                    f"Se generaron/actualizaron {consolidated_count} certificaciones mensuales automaticamente.",
                )

    progress_done_units += 1
    push_progress(
        "Consolidacion finalizada. Registrando auditoria...",
        stage_index=4,
        stage_label="Finalizacion",
    )

    record_action(
        "VALIDATION",
        request=request,
        module="Validation",
        object_repr=f"HistÃ³rico {batch.dataset_type.name} | {batch.entity.code or batch.entity.name}",
        details=(
            f"AprobaciÃ³n masiva ({len(instance_ids)} instancias), "
            f"materializadas={materialized_ok}, errores={materialize_errors}, "
            f"certificaciones={consolidated_count}, archivos_limpiados={cleaned_files_count}"
        ),
    )
    progress_done_units += 1
    push_progress(
        "Aprobacion historica completada.",
        status="DONE",
        percent_override=100,
        stage_index=4,
        stage_label="Completado",
        timeout=300,
    )
    return _json_or_redirect(request, "validation:inbox")


@login_required
def approve_historical_batch_progress(request, batch_id: int):
    batch = (
        HistoricalImportBatch.objects.select_related("dataset_type", "entity")
        .filter(pk=batch_id)
        .first()
    )
    if not batch or batch.dataset_type.validation_frequency != DatasetType.DAILY:
        return JsonResponse({"ok": False, "error": "No autorizado."}, status=403)

    user = request.user
    can_validate = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_daily=True,
    ).filter(Q(entity=batch.entity) | Q(entity__isnull=True)).exists()
    if not can_validate:
        return JsonResponse({"ok": False, "error": "No autorizado."}, status=403)

    payload = _get_historical_approve_progress(user.id, batch.id) or {
        "status": "IDLE",
        "percent": 0,
        "message": "Esperando inicio del proceso...",
        "error": "",
        "redirect_url": "",
        "stage_index": None,
        "stage_total": 4,
        "stage_label": "",
    }

    return JsonResponse({"ok": True, **payload})


@login_required
def admin_overview(request):
    """
    Historial y estado de validaciones para Administracion,
    separado en datasets diarios y mensuales.
    """
    if not (
        request.user.is_superuser
        or Membership.objects.filter(user=request.user, role="ADMIN", is_active=True).exists()
    ):
        return redirect("validation:inbox")

    daily_instances = (
        DatasetInstance.objects.select_related("dataset_type", "entity")
        .filter(dataset_type__validation_frequency=DatasetType.DAILY)
        .order_by("-created_at")[:100]
    )
    monthly_instances = (
        DatasetInstance.objects.select_related("dataset_type", "entity")
        .filter(
            dataset_type__validation_frequency__in=[
                DatasetType.WEEKLY,
                DatasetType.MONTHLY,
                DatasetType.FLEXIBLE,
            ]
        )
        .order_by("-created_at")[:100]
    )
    certification_status = collect_certification_status()

    return render(
        request,
        "validate/admin_overview.html",
        {
            "daily_instances": daily_instances,
            "monthly_instances": monthly_instances,
            "certification_status": certification_status,
        },
    )


@login_required
def detail(request, pk):
    instance = get_object_or_404(
        DatasetInstance.objects.select_related("dataset_type", "entity"),
        pk=pk,
    )

    freq = instance.dataset_type.validation_frequency

    base_qs = Membership.objects.filter(user=request.user, role="VALIDATOR", is_active=True)
    if freq == DatasetType.DAILY:
        base_qs = base_qs.filter(can_validate_daily=True)
    elif freq == DatasetType.WEEKLY:
        base_qs = base_qs.filter(can_validate_weekly=True)
    elif freq == DatasetType.FLEXIBLE:
        base_qs = base_qs.filter(can_validate_projections=True)
    else:
        base_qs = base_qs.filter(can_validate_monthly=True)

    # Primero intentamos un membership especifico por entidad; si no hay, usamos uno global
    if instance.entity_id:
        membership = base_qs.filter(entity=instance.entity).order_by("validation_level").first()
    else:
        membership = None
    if not membership:
        membership = base_qs.filter(entity__isnull=True).order_by("validation_level").first()


    if not membership:
        messages.error(request, "No tiene permisos de validacion sobre este dataset.")
        return redirect(reverse("validation:inbox"))

    if (
        instance.dataset_type.validation_frequency == DatasetType.MONTHLY
        and instance.dataset_type.is_certification
    ):
        profile = getattr(request.user, "profile", None)
        if profile:
            profile.last_seen_certification_alert = timezone.now()
            profile.save(update_fields=["last_seen_certification_alert"])
            invalidate_admin_flags_cache(request.user.id)

    if request.method == "POST":
        form = ValidationDecisionForm(request.POST)
        if form.is_valid():
            action: ValidationAction = form.save(commit=False)
            action.dataset_instance = instance
            action.validator = membership
            action.user = request.user
            action.level = membership.validation_level if membership.validation_level else 1
            action.save()

            if action.decision == ValidationAction.DECISION_APPROVE:
                freq = instance.dataset_type.validation_frequency

                if freq == DatasetType.DAILY:
                    # Flujo diario: un solo nivel (Jefe de planta)
                    instance.state = DatasetInstance.STATE_PUBLISHED
                else:
                    # Flujo semanal/mensual: requiere todas las instituciones
                    instance.state = determine_periodic_state(instance)

                instance.save()

                if instance.state == DatasetInstance.STATE_PUBLISHED:
                    materialize_instance(instance)
                    try:
                        cleanup_files_after_publication(
                            instance_ids={instance.id},
                            batch_ids=(
                                {instance.historical_batch_id}
                                if instance.historical_batch_id
                                else None
                            ),
                            apply_changes=True,
                        )
                    except Exception:
                        logger.exception(
                            "Error limpiando archivos tras publicar instancia (instance=%s).",
                            instance.id,
                        )
                    if freq == DatasetType.DAILY:
                        try:
                            consolidate_certifications_for_daily_periods(
                                instance.dataset_type,
                                instance.entity,
                                [instance.period],
                                request=request,
                            )
                        except Exception:
                            logger.exception(
                                "Error consolidando certificaciones tras aprobar diario (instance=%s).",
                                instance.id,
                            )
                            messages.warning(
                                request,
                                "El dia fue aprobado, pero fallo la consolidacion mensual automatica.",
                            )
                messages.success(request, "Dataset aprobado correctamente.")
                record_action(
                    "VALIDATION",
                    request=request,
                    module="Validation",
                    object_repr=f"{instance.dataset_type.name} | {instance.period}",
                    details="Aprobado",
                )
                return redirect(reverse("validation:inbox"))
            else:
                instance.state = DatasetInstance.STATE_DRAFT
                error_summary = (action.comment or "").strip()
                if not error_summary:
                    error_summary = "Rechazado sin comentarios. Revisa y corrige antes de reenviar."
                instance.last_error_summary = error_summary
                instance.submitted_at = None
                instance.save()
                messages.warning(request, "Dataset rechazado y devuelto a borrador.")
                record_action(
                    "VALIDATION",
                    request=request,
                    module="Validation",
                    object_repr=f"{instance.dataset_type.name} | {instance.period}",
                    details="Rechazado",
                )
                return redirect(reverse("validation:inbox"))
    else:
        form = ValidationDecisionForm()

    actions = instance.validation_actions.select_related("user").all()
    change_requests = (
        instance.change_requests.select_related("submitted_by__user")
        .prefetch_related("attachments")
        .all()
    )
    monthly_review = None
    if (
        instance.dataset_type.validation_frequency == DatasetType.MONTHLY
        and instance.dataset_type.source_dataset
    ):
        monthly_review = _build_monthly_review_context(instance)

    return render(
        request,
        "validate/detail.html",
        {
            "instance": instance,
            "form": form,
            "actions": actions,
            "change_requests": change_requests,
            "monthly_review": monthly_review,
        },
    )
