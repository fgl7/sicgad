from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

import json

from audit.utils import record_action

from accounts.decorators import admin_required
from performance.models import (
    FREQ_DAILY,
    FREQ_MONTHLY,
    FREQ_WEEKLY,
    FREQ_YEARLY,
    PerformanceIndicator,
    PerformanceIndicatorInput,
    PerformanceIndicatorResult,
    PerformanceVariableMapping,
)
from performance.services import MonthWindow, compute_indicator, evaluate_expression, month_window, shift_months
from plants.models import Plant
from schemas.models import ColumnDef, DatasetType


def _parse_month(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        y_s, m_s = raw.split("-", 1)
        y = int(y_s)
        m = int(m_s)
        if m < 1 or m > 12:
            return None
        return y, m
    except Exception:
        return None


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        y_s, m_s, d_s = raw.split("-", 2)
        y = int(y_s)
        m = int(m_s)
        d = int(d_s)
        return date(y, m, d)
    except Exception:
        return None


def _parse_frequency(raw: str | None) -> str:
    if not raw:
        return FREQ_MONTHLY
    raw = raw.strip().upper()
    if raw in {FREQ_DAILY, FREQ_WEEKLY, FREQ_MONTHLY, FREQ_YEARLY}:
        return raw
    return FREQ_MONTHLY


def _get_date_range(frequency: str, start_raw: str | None, end_raw: str | None) -> tuple[date, date]:
    today = timezone.now().date()
    end_date = _parse_day(end_raw) or today
    start_date = _parse_day(start_raw)
    if start_date is None:
        base_month = date(end_date.year, end_date.month, 1)
        if frequency == FREQ_DAILY:
            start_date = end_date - timedelta(days=180)
        elif frequency == FREQ_WEEKLY:
            start_date = end_date - timedelta(weeks=26)
        elif frequency == FREQ_YEARLY:
            start_date = date(end_date.year - 4, 1, 1)
        else:
            start_date = shift_months(base_month, -11)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


def _build_periods(
    frequency: str, start_date: date, end_date: date
) -> tuple[list[tuple[date, date]], list[str], str]:
    periods: list[tuple[date, date]] = []
    labels: list[str] = []

    if frequency == FREQ_DAILY:
        day = start_date
        while day <= end_date:
            periods.append((day, day))
            labels.append(day.strftime("%Y-%m-%d"))
            day += timedelta(days=1)
        title = f"Historico ({start_date:%Y-%m-%d} a {end_date:%Y-%m-%d})"
        return periods, labels, title

    if frequency == FREQ_WEEKLY:
        current = start_date
        while current <= end_date:
            period_end = min(current + timedelta(days=6), end_date)
            periods.append((current, period_end))
            labels.append(f"{current:%Y-%m-%d}")
            current = period_end + timedelta(days=1)
        title = f"Historico ({start_date:%Y-%m-%d} a {end_date:%Y-%m-%d})"
        return periods, labels, title

    if frequency == FREQ_YEARLY:
        year = start_date.year
        while year <= end_date.year:
            period_start = date(year, 1, 1)
            period_end = date(year, 12, 31)
            if year == start_date.year:
                period_start = start_date
            if year == end_date.year:
                period_end = end_date
            periods.append((period_start, period_end))
            labels.append(f"{year}")
            year += 1
        title = f"Historico ({start_date:%Y} a {end_date:%Y})"
        return periods, labels, title

    month_starts: list[date] = []
    current = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while current <= end_month:
        month_starts.append(current)
        current = shift_months(current, 1)
    for m in month_starts:
        periods.append((date(m.year, m.month, 1), month_window(m.year, m.month).period_end))
        labels.append(m.strftime("%Y-%m"))
    title = f"Historico ({month_starts[0]:%Y-%m} a {end_month:%Y-%m})"
    return periods, labels, title


def _parse_expression_tokens(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    tokens = []
    for t in data:
        token = str(t).strip()
        if token:
            tokens.append(token)
    return tokens


def _build_indicator_key(plant: Plant, label: str) -> str:
    base = slugify(f"{plant.code}-{label}")[:70].strip("-")
    if not base:
        base = slugify(plant.code)[:20] or "formula"
    key = base
    counter = 1
    while PerformanceIndicator.objects.filter(key=key).exists():
        counter += 1
        suffix = f"-{counter}"
        key = f"{base[: max(1, 80 - len(suffix))]}{suffix}"
    return key



def _daily_history_days(base_day: date, months: int = 6) -> list[date]:
    start_month = shift_months(date(base_day.year, base_day.month, 1), -(months - 1))
    day = start_month
    days: list[date] = []
    while day <= base_day:
        days.append(day)
        day += timedelta(days=1)
    return days


def _upsert_indicator_result(
    *,
    indicator: PerformanceIndicator,
    plant: Plant,
    window,
    stage: str,
    frequency: str,
    value: float | None,
    status: str,
    trace: dict,
) -> PerformanceIndicatorResult:
    result, _ = PerformanceIndicatorResult.objects.update_or_create(
        indicator=indicator,
        plant=plant,
        period_end=window.period_end,
        frequency=frequency,
        defaults={
            "period_start": window.period_start,
            "stage": stage,
            "status": status,
            "numeric_value": value,
            "text_value": "",
            "trace": trace,
        },
    )
    return result


@admin_required
def kcl_formula_9(request: HttpRequest) -> HttpResponse:
    return formula_builder(request)


@admin_required
def formula_builder(request: HttpRequest) -> HttpResponse:
    plants = Plant.objects.order_by("code")
    if not plants.exists():
        messages.error(request, "No existen plantas registradas.")
        return redirect("home")
    plant_id = request.POST.get("plant_id") or request.GET.get("plant_id")
    plant = Plant.objects.filter(id=plant_id).first() if plant_id else plants.first()
    if not plant:
        messages.error(request, "No existe la planta seleccionada.")
        return redirect("home")
    formulas_qs = PerformanceIndicator.objects.filter(plant=plant).order_by("label")
    formula_id = request.POST.get("formula_id") or request.GET.get("formula_id")
    indicator = formulas_qs.filter(id=formula_id).first() if formula_id else formulas_qs.first()
    action = request.POST.get("action") if request.method == "POST" else None
    recalculate = request.GET.get("recalculate") == "1"
    if action == "create_formula":
        label = (request.POST.get("label") or "").strip()
        description = (request.POST.get("description") or "").strip()
        unit = (request.POST.get("unit") or "").strip()
        frequency = _parse_frequency(request.POST.get("frequency"))
        if not label:
            messages.error(request, "Debe ingresar un nombre para la formula.")
        else:
            key = _build_indicator_key(plant, label)
            indicator = PerformanceIndicator.objects.create(
                key=key,
                plant=plant,
                label=label,
                unit=unit,
                description=description,
                formula_text=description,
                frequency=frequency,
                is_active=True,
            )
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{plant.code}:{indicator.key}",
                details="Formula creada desde UI",
            )
            messages.success(request, "Formula creada.")
        return redirect(f"/performance/formulas/?plant_id={plant.id}&formula_id={indicator.id if indicator else ''}")
    if not indicator:
        indicator = None
    if action == "update_formula" and indicator:
        label = (request.POST.get("label") or "").strip()
        description = (request.POST.get("description") or "").strip()
        unit = (request.POST.get("unit") or "").strip()
        frequency = _parse_frequency(request.POST.get("frequency"))
        if label:
            indicator.label = label
        indicator.description = description
        indicator.formula_text = description
        indicator.unit = unit
        indicator.frequency = frequency
        indicator.save(update_fields=["label", "description", "formula_text", "unit", "frequency", "updated_at"])
        record_action(
            "OTHER",
            request=request,
            module="performance",
            object_repr=f"{plant.code}:{indicator.key}",
            details="Formula actualizada desde UI",
        )
        messages.success(request, "Formula actualizada.")
        return redirect(
            f"/performance/formulas/?plant_id={plant.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "add_input" and indicator:
        column_id = request.POST.get("column_id")
        column = ColumnDef.objects.filter(
            id=column_id,
            dataset_type__plant=plant,
            dataset_type__status=DatasetType.STATUS_APPROVED,
            dataset_type__is_active=True,
            is_active=True,
        ).select_related("dataset_type").first()
        if not column:
            messages.error(request, "Seleccione una columna valida.")
        else:
            existing_tokens = set(
                indicator.inputs.filter(is_active=True).values_list("token", flat=True)
            )
            token_idx = 1
            token = f"v{token_idx}"
            while token in existing_tokens:
                token_idx += 1
                token = f"v{token_idx}"
            PerformanceIndicatorInput.objects.create(
                indicator=indicator,
                token=token,
                column=column,
                label=column.label,
            )
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{plant.code}:{indicator.key}",
                details=f"Variable agregada: {token} -> {column.name}",
            )
            messages.success(request, "Variable agregada.")
            recalculate = True
        return redirect(
            f"/performance/formulas/?plant_id={plant.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "remove_input" and indicator:
        input_id = request.POST.get("input_id")
        input_obj = indicator.inputs.filter(id=input_id).first()
        if input_obj:
            input_obj.delete()
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{plant.code}:{indicator.key}",
                details=f"Variable eliminada: {input_obj.token}",
            )
            messages.success(request, "Variable eliminada.")
            recalculate = True
        return redirect(
            f"/performance/formulas/?plant_id={plant.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "save_input" and indicator:
        input_id = request.POST.get("input_id")
        inp = indicator.inputs.filter(id=input_id).select_related("column", "column__dataset_type").first()
        if inp:
            column_id = request.POST.get("column_id")
            aggregation = request.POST.get("aggregation") or inp.aggregation
            transform = request.POST.get("transform") or inp.transform
            transform_value_raw = request.POST.get("transform_value")
            offset_raw = request.POST.get("offset_periods")
            column = (
                ColumnDef.objects.filter(
                    id=column_id,
                    dataset_type__plant=plant,
                    dataset_type__status=DatasetType.STATUS_APPROVED,
                    dataset_type__is_active=True,
                    is_active=True,
                )
                .select_related("dataset_type")
                .first()
                if column_id
                else inp.column
            )
            inp.column = column or inp.column
            inp.aggregation = aggregation
            inp.transform = transform
            inp.transform_value = float(transform_value_raw) if transform_value_raw else None
            inp.offset_periods = int(offset_raw) if offset_raw else 0
            inp.save(
                update_fields=["column", "aggregation", "transform", "transform_value", "offset_periods", "updated_at"]
            )
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{plant.code}:{indicator.key}",
                details=f"Variable actualizada: {inp.token}",
            )
            messages.success(request, "Variable actualizada.")
        return redirect(
            f"/performance/formulas/?plant_id={plant.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "save_formula" and indicator:
        tokens = _parse_expression_tokens(request.POST.get("expression_tokens"))
        inputs = list(indicator.inputs.filter(is_active=True).values_list("token", flat=True))
        allowed_tokens = set(inputs)
        allowed_ops = {"+", "-", "*", "/", "(", ")"}
        invalid = []
        for tok in tokens:
            if tok in allowed_ops:
                continue
            if tok in allowed_tokens:
                continue
            try:
                float(tok)
            except Exception:
                invalid.append(tok)
        if invalid:
            messages.error(request, "Tokens invalidos: " + ", ".join(invalid))
        else:
            placeholder_values = {token: 1.0 for token in allowed_tokens}
            _, err = evaluate_expression(tokens, placeholder_values)
            if err:
                messages.error(request, f"Expresion invalida: {err}")
            else:
                indicator.expression = tokens
                indicator.expression_text = " ".join(tokens)
                indicator.save(update_fields=["expression", "expression_text", "updated_at"])
                record_action(
                    "OTHER",
                    request=request,
                    module="performance",
                    object_repr=f"{plant.code}:{indicator.key}",
                    details="Formula actualizada (expresion)",
                )
                messages.success(request, "Formula guardada.")
                recalculate = True
        return redirect(
            f"/performance/formulas/?plant_id={plant.id}&formula_id={indicator.id}&recalculate=1"
        )
    frequency = _parse_frequency(request.GET.get("frequency") or (indicator.frequency if indicator else None))
    start_date, end_date = _get_date_range(
        frequency, request.GET.get("date_start"), request.GET.get("date_end")
    )
    periods: list[tuple[date, date]] = []
    chart_labels: list[str] = []
    chart_title = ""
    if indicator:
        periods, chart_labels, chart_title = _build_periods(frequency, start_date, end_date)
    chart_values: list[float | None] = []
    if indicator and periods:
        period_ends = [p[1] for p in periods]
        results_qs = PerformanceIndicatorResult.objects.filter(
            indicator=indicator,
            plant=plant,
            frequency=frequency,
            period_end__gte=period_ends[0],
            period_end__lte=period_ends[-1],
        )
        existing = {r.period_end: r for r in results_qs}
        if recalculate or len(existing) != len(period_ends):
            for period_start, period_end in periods:
                w = MonthWindow(period_start, period_end)
                value, status, trace = compute_indicator(indicator, w, frequency=frequency)
                _upsert_indicator_result(
                    indicator=indicator,
                    plant=plant,
                    window=w,
                    stage="DRAFT",
                    frequency=frequency,
                    value=value,
                    status=status,
                    trace=trace,
                )
            results_qs = PerformanceIndicatorResult.objects.filter(
                indicator=indicator,
                plant=plant,
                frequency=frequency,
                period_end__gte=period_ends[0],
                period_end__lte=period_ends[-1],
            )
            existing = {r.period_end: r for r in results_qs}
        for period_end in period_ends:
            res = existing.get(period_end)
            chart_values.append(res.numeric_value if res else None)
    column_options = list(
        ColumnDef.objects.filter(
            dataset_type__plant=plant,
            dataset_type__status=DatasetType.STATUS_APPROVED,
            dataset_type__is_active=True,
            is_active=True,
        )
        .select_related("dataset_type")
        .order_by("dataset_type__name", "display_order", "label", "name")
    )
    inputs = (
        list(
            indicator.inputs.filter(is_active=True)
            .select_related("column", "column__dataset_type")
            .order_by("token")
        )
        if indicator
        else []
    )
    context = {
        "plant": plant,
        "plants": list(plants),
        "formulas": list(formulas_qs),
        "indicator": indicator,
        "inputs": inputs,
        "column_options": column_options,
        "aggregation_choices": PerformanceVariableMapping.AGG_CHOICES,
        "transform_choices": PerformanceVariableMapping.TRANSFORM_CHOICES,
        "frequency": frequency,
        "date_start": start_date.strftime("%Y-%m-%d"),
        "date_end": end_date.strftime("%Y-%m-%d"),
        "chart_title": chart_title or "Resultado del Calculo de Indicador",
        "chart_labels_json": json.dumps(chart_labels),
        "chart_values_json": json.dumps(chart_values),
        "expression_tokens_json": json.dumps(indicator.expression if indicator else []),
    }
    return render(request, "performance/formulas.html", context)
