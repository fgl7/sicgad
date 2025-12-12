import calendar
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from ingest.models import DatasetInstance, PublishedDataPoint
from ingest.utils import materialize_instance
from schemas.models import DatasetType
from schemas.services import collect_certification_status, previous_month_range

from audit.utils import record_action
from .forms import ValidationDecisionForm
from .models import ValidationAction
from .services import determine_monthly_state


PUBLISHED_STATES = [
    DatasetInstance.STATE_PUBLISHED,
    DatasetInstance.STATE_LOCKED,
]


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
            plant=instance.plant,
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
    Los administradores usarán una vista de resumen separada.
    """
    user = request.user

    if user.is_superuser or Membership.objects.filter(
        user=user, role="ADMIN", is_active=True
    ).exists():
        return redirect("validation:admin_overview")

    # Si el usuario no es validador, lo redirigimos al historial de cargas,
    # donde podrá ver el estado y comentarios de sus datasets.
    is_validator = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
    ).exists()
    if not is_validator:
        messages.info(
            request,
            "La bandeja de validación está disponible solo para validadores. "
            "Puedes revisar el estado y comentarios de tus cargas en el historial.",
        )
        return redirect("ingest:upload_history")

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

    base_qs = DatasetInstance.objects.select_related("dataset_type", "plant").filter(
        state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1]
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
        monthly_filter |= Q(dataset_type__validation_frequency=DatasetType.MONTHLY)

    approval_subquery = ValidationAction.objects.filter(
        dataset_instance=OuterRef("pk"),
        user=user,
        decision=ValidationAction.DECISION_APPROVE,
    )
    approval_since_submit = approval_subquery.filter(created_at__gte=OuterRef("submitted_at"))

    items = (
        base_qs.filter(daily_filter | monthly_filter)
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
            "dataset_instance__plant",
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
            DatasetInstance.objects.select_related("dataset_type", "plant")
            .filter(
                dataset_type__validation_frequency=DatasetType.MONTHLY,
                dataset_type__is_certification=True,
                period=previous_month_end,
                state__in=pending_cert_states,
            )
            .order_by("plant__code", "dataset_type__name")
        )
        if not has_global_monthly:
            if monthly_plants:
                cert_qs = cert_qs.filter(plant_id__in=monthly_plants)
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

    return render(
        request,
        "validate/inbox.html",
        {
            "items": items,
            "history_actions": history_actions,
            "certification_alerts": certification_alerts,
        },
    )


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
        DatasetInstance.objects.select_related("dataset_type", "plant")
        .filter(dataset_type__validation_frequency=DatasetType.DAILY)
        .order_by("-created_at")[:100]
    )
    monthly_instances = (
        DatasetInstance.objects.select_related("dataset_type", "plant")
        .filter(dataset_type__validation_frequency=DatasetType.MONTHLY)
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
        DatasetInstance.objects.select_related("dataset_type", "plant"),
        pk=pk,
    )

    freq = instance.dataset_type.validation_frequency

    base_qs = Membership.objects.filter(user=request.user, role="VALIDATOR", is_active=True)
    if freq == DatasetType.DAILY:
        base_qs = base_qs.filter(can_validate_daily=True)
    else:
        base_qs = base_qs.filter(can_validate_monthly=True)

    # Primero intentamos un membership especifico de planta; si no hay, usamos uno global
    membership = base_qs.filter(plant=instance.plant).order_by("validation_level").first()
    if not membership:
        membership = base_qs.filter(plant__isnull=True).order_by("validation_level").first()

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
                    # Flujo mensual / general: requiere todas las instituciones
                    instance.state = determine_monthly_state(instance)

                instance.save()

                if instance.state == DatasetInstance.STATE_PUBLISHED:
                    materialize_instance(instance)
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
