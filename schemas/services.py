from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Iterable, List, Optional

from django.db import transaction
from django.db.models import Max, Min, Sum
from django.utils import timezone

from audit.utils import record_action
from ingest.models import DatasetInstance, PublishedDataPoint
from accounts.models import Membership
from .models import DatasetType


PUBLISHED_STATES = [
    DatasetInstance.STATE_PUBLISHED,
    DatasetInstance.STATE_LOCKED,
]

_last_checked_period: Optional[date] = None


def previous_month_range(reference_date: Optional[date] = None) -> tuple[date, date]:
    """
    Devuelve una tupla (primer_dÃ­a, Ãºltimo_dÃ­a) del mes anterior a la fecha de referencia.
    """
    if reference_date is None:
        reference_date = timezone.now().date()

    first_day_current_month = reference_date.replace(day=1)
    last_day_previous = first_day_current_month - timedelta(days=1)
    first_day_previous = last_day_previous.replace(day=1)
    return first_day_previous, last_day_previous


def consolidate_latest_month(
    schema: DatasetType,
    reference_date: Optional[date] = None,
    request=None,
) -> Optional[DatasetInstance]:
    """
    Consolida automÃ¡ticamente el mes anterior para un esquema de certificaciÃ³n especÃ­fico.
    Retorna la instancia mensual creada/actualizada o None si no hay datos para consolidar.
    """
    if not schema.is_certification or not schema.source_dataset:
        return None

    month_start, month_end = previous_month_range(reference_date)
    return _consolidate_schema_for_period(schema, month_start, month_end, request=request)


def consolidate_month_for_period(
    schema: DatasetType,
    period: date,
    request=None,
) -> Optional[DatasetInstance]:
    """
    Consolida el mes de la fecha indicada para un esquema de certificacion.
    """
    if not schema.is_certification or not schema.source_dataset:
        return None

    month_start = period.replace(day=1)
    month_end = period.replace(day=monthrange(period.year, period.month)[1])
    return _consolidate_schema_for_period(schema, month_start, month_end, request=request)


def consolidate_certifications_for_daily_periods(
    source_dataset: DatasetType,
    entity,
    periods: Iterable[date],
    request=None,
) -> List[DatasetInstance]:
    """
    Consolida certificaciones mensuales afectadas por uno o mas dias diarios publicados.
    """
    month_ends = sorted(
        {
            p.replace(day=monthrange(p.year, p.month)[1])
            for p in periods
            if isinstance(p, date)
        }
    )
    if not month_ends:
        return []

    schemas = (
        DatasetType.objects.filter(
            is_certification=True,
            validation_frequency=DatasetType.MONTHLY,
            source_dataset=source_dataset,
            entity=entity,
        )
        .select_related("source_dataset", "entity")
        .order_by("id")
    )
    if not schemas.exists():
        return []

    results: List[DatasetInstance] = []
    for schema in schemas:
        for month_end in month_ends:
            instance = consolidate_month_for_period(schema, month_end, request=request)
            if instance:
                results.append(instance)
    return results


def backfill_certification_schema(
    schema: DatasetType,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    request=None,
) -> List[DatasetInstance]:
    """
    Ejecuta consolidacion historica mensual para un esquema de certificacion.
    """
    if not schema.is_certification or not schema.source_dataset:
        return []

    source = schema.source_dataset
    daily_qs = DatasetInstance.objects.filter(
        dataset_type=source,
        entity=schema.entity,
        state__in=PUBLISHED_STATES,
    )
    if from_date:
        daily_qs = daily_qs.filter(period__gte=from_date)
    if to_date:
        daily_qs = daily_qs.filter(period__lte=to_date)

    bounds = daily_qs.aggregate(min_period=Min("period"), max_period=Max("period"))
    min_period = bounds["min_period"]
    max_period = bounds["max_period"]
    if not min_period or not max_period:
        return []

    cursor = min_period.replace(day=1)
    max_month_end = max_period.replace(day=monthrange(max_period.year, max_period.month)[1])

    results: List[DatasetInstance] = []
    while cursor <= max_month_end:
        month_end = cursor.replace(day=monthrange(cursor.year, cursor.month)[1])
        instance = consolidate_month_for_period(schema, month_end, request=request)
        if instance:
            results.append(instance)
        cursor = (month_end + timedelta(days=1)).replace(day=1)
    return results


def backfill_all_certifications(
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    request=None,
) -> List[DatasetInstance]:
    """
    Ejecuta backfill historico para todos los esquemas de certificacion.
    """
    results: List[DatasetInstance] = []
    schemas = DatasetType.objects.filter(
        is_certification=True,
        validation_frequency=DatasetType.MONTHLY,
        source_dataset__isnull=False,
    ).select_related("source_dataset", "entity")
    for schema in schemas:
        results.extend(
            backfill_certification_schema(
                schema,
                from_date=from_date,
                to_date=to_date,
                request=request,
            )
        )
    return results


def consolidate_all_certifications(
    reference_date: Optional[date] = None,
    request=None,
) -> List[DatasetInstance]:
    """
    Consolida el mes anterior para todos los esquemas de certificaciÃ³n configurados.
    """
    results: List[DatasetInstance] = []
    for schema in DatasetType.objects.filter(
        is_certification=True,
        validation_frequency=DatasetType.MONTHLY,
        source_dataset__isnull=False,
    ).select_related("source_dataset", "entity"):
        instance = consolidate_latest_month(schema, reference_date, request=request)
        if instance:
            results.append(instance)
    return results


def ensure_previous_month_consolidated(reference_date: Optional[date] = None) -> None:
    """
    Asegura que el mes anterior estÃ© consolidado al menos una vez por ciclo de aplicaciÃ³n.
    Se usa para disparar consolidaciones automÃ¡ticas al iniciar sesiones (lazy).
    """
    global _last_checked_period

    _, period_end = previous_month_range(reference_date)
    if _last_checked_period == period_end:
        return

    consolidate_all_certifications(reference_date=reference_date)
    _last_checked_period = period_end


def collect_certification_status() -> List[dict]:
    """
    Construye un resumen con el estado de consolidaciÃ³n y cobertura diaria por esquema de certificaciÃ³n.
    """
    status: List[dict] = []
    schemas = (
        DatasetType.objects.filter(
            is_certification=True,
            validation_frequency=DatasetType.MONTHLY,
            source_dataset__isnull=False,
        )
        .select_related("entity", "source_dataset")
        .order_by("entity__name", "name")
    )
    for schema in schemas:
        source = schema.source_dataset
        latest_daily = None
        if source:
            latest_daily = (
                DatasetInstance.objects.filter(
                    dataset_type=source,
                    entity=schema.entity,
                    state__in=PUBLISHED_STATES,
                ).aggregate(max_period=Max("period"))["max_period"]
            )
        status.append(
            {
                "schema": schema,
                "latest_daily_period": latest_daily,
                "last_consolidated_period": schema.last_consolidated_period,
            }
        )
    return status


def _consolidate_schema_for_period(
    schema: DatasetType,
    month_start: date,
    month_end: date,
    request=None,
) -> Optional[DatasetInstance]:
    source = schema.source_dataset
    if source is None:
        return None

    daily_instances = DatasetInstance.objects.filter(
        dataset_type=source,
        entity=schema.entity,
        state__in=PUBLISHED_STATES,
        period__gte=month_start,
        period__lte=month_end,
    )
    if not daily_instances.exists():
        return None

    pending_daily = DatasetInstance.objects.filter(
        dataset_type=source,
        entity=schema.entity,
        period__gte=month_start,
        period__lte=month_end,
    ).exclude(state__in=PUBLISHED_STATES)

    if pending_daily.exists():
        existing = DatasetInstance.objects.filter(
            dataset_type=schema,
            entity=schema.entity,
            period=month_end,
        ).first()
        if existing and existing.state != DatasetInstance.STATE_PUBLISHED:
            existing.state = DatasetInstance.STATE_DRAFT
            existing.last_error_summary = "Pendiente consolidar: faltan datos diarios aprobados para el mes."
            existing.save(update_fields=["state", "last_error_summary"])
        return None

    required_dates = set()
    current = month_start
    while current <= month_end:
        required_dates.add(current)
        current += timedelta(days=1)
    available_dates = set(
        daily_instances.values_list("period", flat=True)
    )
    if not required_dates.issubset(available_dates):
        return None

    loader_membership = (
        Membership.objects.filter(
            role="LOADER",
            is_active=True,
            entity=schema.entity,
        )
        .order_by("id")
        .first()
    )

    # Las certificaciones automaticas deben ingresar al flujo de validacion.
    initial_state = DatasetInstance.STATE_SUBMITTED

    with transaction.atomic():
        instance, created = DatasetInstance.objects.get_or_create(
            dataset_type=schema,
            entity=schema.entity,
            period=month_end,
            defaults={
                "state": initial_state,
                "row_count": 0,
                "error_count": 0,
                "last_error_summary": "",
            },
        )
        instance.row_count = 1
        instance.error_count = 0
        instance.last_error_summary = ""
        if created:
            instance.state = initial_state
        if loader_membership and instance.created_by_id is None:
            instance.created_by = loader_membership
        instance.save()

        PublishedDataPoint.objects.filter(instance=instance).delete()

        matching_columns = {
            col.name: col for col in source.columns.filter(is_active=True)
        }
        points_to_create: List[PublishedDataPoint] = []
        for column in schema.columns.filter(is_active=True):
            matching = matching_columns.get(column.name)
            if not matching:
                continue

            column_points = PublishedDataPoint.objects.filter(
                instance__dataset_type=source,
                instance__entity=schema.entity,
                instance__period__gte=month_start,
                instance__period__lte=month_end,
                column=matching,
            )
            if not column_points.exists():
                continue

            numeric_value = None
            text_value = ""
            date_value = None
            bool_value = None

            if column.data_type in ("INTEGER", "FLOAT"):
                total = column_points.aggregate(total=Sum("numeric_value"))["total"]
                numeric_value = float(total or 0)
            elif column.data_type == "BOOLEAN":
                bool_value = column_points.filter(bool_value=True).exists()
            elif column.data_type == "DATE":
                date_value = month_end
            else:
                text_value = (
                    column_points.exclude(text_value="")
                    .order_by("-instance__period", "-row_index")
                    .values_list("text_value", flat=True)
                    .first()
                    or f"Consolidado {month_start:%Y-%m}"
                )

            points_to_create.append(
                PublishedDataPoint(
                    instance=instance,
                    column=column,
                    row_index=1,
                    numeric_value=numeric_value,
                    text_value=text_value,
                    date_value=date_value,
                    bool_value=bool_value,
                )
            )

        if points_to_create:
            PublishedDataPoint.objects.bulk_create(points_to_create, batch_size=500)

        schema.last_consolidated_period = month_end
        schema.save(update_fields=["last_consolidated_period"])

        record_action(
            "SCHEMA",
            request=request,
            module="Schemas",
            object_repr=f"ConsolidaciÃ³n {schema.name} {month_start:%Y-%m}",
            details=f"Instancia mensual generada para {schema.entity.name}",
        )

        return instance

