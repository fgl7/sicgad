from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import List, Optional

from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from audit.utils import record_action
from ingest.models import DatasetInstance, PublishedDataPoint
from .models import DatasetType


PUBLISHED_STATES = [
    DatasetInstance.STATE_PUBLISHED,
    DatasetInstance.STATE_LOCKED,
]

_last_checked_period: Optional[date] = None


def previous_month_range(reference_date: Optional[date] = None) -> tuple[date, date]:
    """
    Devuelve una tupla (primer_día, último_día) del mes anterior a la fecha de referencia.
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
    Consolida automáticamente el mes anterior para un esquema de certificación específico.
    Retorna la instancia mensual creada/actualizada o None si no hay datos para consolidar.
    """
    if not schema.is_certification or not schema.source_dataset:
        return None

    month_start, month_end = previous_month_range(reference_date)
    return _consolidate_schema_for_period(schema, month_start, month_end, request=request)


def consolidate_all_certifications(
    reference_date: Optional[date] = None,
    request=None,
) -> List[DatasetInstance]:
    """
    Consolida el mes anterior para todos los esquemas de certificación configurados.
    """
    results: List[DatasetInstance] = []
    for schema in DatasetType.objects.filter(
        is_certification=True,
        validation_frequency=DatasetType.MONTHLY,
        source_dataset__isnull=False,
    ).select_related("source_dataset", "plant"):
        instance = consolidate_latest_month(schema, reference_date, request=request)
        if instance:
            results.append(instance)
    return results


def ensure_previous_month_consolidated(reference_date: Optional[date] = None) -> None:
    """
    Asegura que el mes anterior esté consolidado al menos una vez por ciclo de aplicación.
    Se usa para disparar consolidaciones automáticas al iniciar sesiones (lazy).
    """
    global _last_checked_period

    _, period_end = previous_month_range(reference_date)
    if _last_checked_period == period_end:
        return

    consolidate_all_certifications(reference_date=reference_date)
    _last_checked_period = period_end


def collect_certification_status() -> List[dict]:
    """
    Construye un resumen con el estado de consolidación y cobertura diaria por esquema de certificación.
    """
    status: List[dict] = []
    schemas = (
        DatasetType.objects.filter(
            is_certification=True,
            validation_frequency=DatasetType.MONTHLY,
            source_dataset__isnull=False,
        )
        .select_related("plant", "source_dataset")
        .order_by("plant__code", "name")
    )
    for schema in schemas:
        source = schema.source_dataset
        latest_daily = None
        if source:
            latest_daily = (
                DatasetInstance.objects.filter(
                    dataset_type=source,
                    plant=schema.plant,
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
        plant=schema.plant,
        state__in=PUBLISHED_STATES,
        period__gte=month_start,
        period__lte=month_end,
    )
    if not daily_instances.exists():
        return None

    with transaction.atomic():
        instance, _ = DatasetInstance.objects.get_or_create(
            dataset_type=schema,
            plant=schema.plant,
            period=month_end,
            defaults={
                "state": DatasetInstance.STATE_SUBMITTED,
                "row_count": 0,
                "error_count": 0,
                "last_error_summary": "",
            },
        )
        instance.state = DatasetInstance.STATE_SUBMITTED
        instance.row_count = 1
        instance.error_count = 0
        instance.last_error_summary = ""
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
                instance__plant=schema.plant,
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
            object_repr=f"Consolidación {schema.name} {month_start:%Y-%m}",
            details=f"Instancia mensual generada para {schema.plant.code}",
        )

        return instance
