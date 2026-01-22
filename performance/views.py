from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import json

from accounts.decorators import admin_required
from performance.forms import ColumnOption, VariableMappingForm
from performance.models import PerformanceIndicator, PerformanceIndicatorResult, PerformanceVariable, PerformanceVariableMapping
from performance.services import MonthWindow, compute_indicator, month_window, shift_months
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
        return PerformanceIndicatorResult.FREQ_MONTHLY
    raw = raw.strip().upper()
    if raw in {PerformanceIndicatorResult.FREQ_DAILY, PerformanceIndicatorResult.FREQ_MONTHLY}:
        return raw
    return PerformanceIndicatorResult.FREQ_MONTHLY


def _get_date_range(frequency: str, start_raw: str | None, end_raw: str | None) -> tuple[date, date]:
    today = timezone.now().date()
    end_date = _parse_day(end_raw) or today
    start_date = _parse_day(start_raw)
    if start_date is None:
        base_month = date(end_date.year, end_date.month, 1)
        if frequency == PerformanceIndicatorResult.FREQ_DAILY:
            start_date = shift_months(base_month, -5)
        else:
            start_date = shift_months(base_month, -11)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date



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
    """
    UI: Formula 9 (KCL) - Rendimiento de Produccion de KCL (%).

    Permite al Admin asignar variables y ver resultados.
    """

    plant = Plant.objects.filter(code="PIKCL").first()
    if not plant:
        messages.error(request, "No existe la planta PIKCL en el sistema.")
        return redirect("home")

    indicator = PerformanceIndicator.objects.filter(key="kcl.yield_pct", plant=plant).first()
    if not indicator:
        messages.error(request, "No existe el indicador kcl.yield_pct. Ejecute seed_performance_catalog.")
        return redirect("home")

    frequency = _parse_frequency(request.GET.get("frequency") if request.method == "GET" else request.POST.get("frequency"))
    start_raw = request.GET.get("date_start") if request.method == "GET" else request.POST.get("date_start")
    end_raw = request.GET.get("date_end") if request.method == "GET" else request.POST.get("date_end")
    start_date, end_date = _get_date_range(frequency, start_raw, end_raw)

    columns_qs = (
        ColumnDef.objects.filter(
            dataset_type__plant=plant,
            dataset_type__status=DatasetType.STATUS_APPROVED,
            dataset_type__is_active=True,
            is_active=True,
        )
        .select_related("dataset_type")
        .order_by("dataset_type__name", "display_order", "label", "name")
    )
    column_options = [
        ColumnOption(
            id=c.id,
            label=f"{c.dataset_type.name} :: {c.label} ({c.name}) [{c.unit or '-'}]",
        )
        for c in columns_qs
    ]

    variables = list(
        PerformanceVariable.objects.filter(
            plant=plant,
            key__in=["kcl.product_mass_tm", "kcl.feed_mass_tm"],
            is_active=True,
        ).order_by("key")
    )
    if not variables:
        messages.error(request, "No existen variables KCL para la formula 9. Ejecute seed_performance_catalog.")
        return redirect("home")

    mappings = list(
        PerformanceVariableMapping.objects.filter(variable__in=variables, is_active=True)
        .select_related("dataset_type", "column")
        .order_by("variable__key", "-updated_at")
    )
    mapping_by_var: dict[int, PerformanceVariableMapping] = {}
    for mapping in mappings:
        if mapping.variable_id not in mapping_by_var:
            mapping_by_var[mapping.variable_id] = mapping

    can_save_mappings = not PerformanceVariableMapping.objects.filter(
        variable__in=variables,
        is_active=True,
    ).exists()

    forms: dict[str, VariableMappingForm] = {}
    for v in variables:
        existing = mapping_by_var.get(v.id)
        initial = {
            "column_id": str(existing.column_id) if existing else "",
            "aggregation": existing.aggregation if existing else "SUM",
            "offset_months": existing.offset_months if existing else 0,
        }
        safe_prefix = v.key.replace(".", "_").replace("-", "_")
        prefix = f"{safe_prefix}"
        if request.method == "POST":
            form = VariableMappingForm(
                request.POST,
                prefix=prefix,
                column_options=column_options,
            )
        else:
            form = VariableMappingForm(
                initial=initial,
                prefix=prefix,
                column_options=column_options,
            )
        if not can_save_mappings:
            for field in form.fields.values():
                field.disabled = True
                field.widget.attrs["disabled"] = True
        forms[v.key] = form

    if request.method == "POST":
        if not can_save_mappings:
            messages.info(request, "Las asignaciones ya fueron configuradas.")
        else:
            all_valid = all(f.is_valid() for f in forms.values())
            if not all_valid:
                messages.error(request, "Hay errores en el formulario. Revise las asignaciones.")
            else:
                with transaction.atomic():
                    for v in variables:
                        form = forms[v.key]
                        column = form.resolve_column()
                        aggregation = form.cleaned_data["aggregation"]
                        offset_months = form.cleaned_data["offset_months"]

                        PerformanceVariableMapping.objects.filter(
                            variable=v,
                            is_active=True,
                        ).update(is_active=False)

                        if column is None:
                            continue

                        dataset = column.dataset_type
                        if dataset.plant_id != plant.id:
                            raise ValueError("Asignacion invalida: la columna no pertenece a la planta PIKCL.")

                        PerformanceVariableMapping.objects.update_or_create(
                            variable=v,
                            dataset_type=dataset,
                            column=column,
                            offset_months=offset_months,
                            stage="DRAFT",
                            defaults={
                                "aggregation": aggregation,
                                "transform": "NONE",
                                "transform_value": None,
                                "notes": "Asignado desde UI (Formula 9 KCL)",
                                "is_active": True,
                            },
                        )

                messages.success(request, "Asignaciones guardadas.")

        redirect_url = f"/performance/kcl/formula-9/?frequency={frequency}"
        redirect_url += f"&date_start={start_date:%Y-%m-%d}&date_end={end_date:%Y-%m-%d}"
        return redirect(redirect_url)

    if frequency == PerformanceIndicatorResult.FREQ_DAILY:
        days = []
        day = start_date
        while day <= end_date:
            days.append(day)
            day += timedelta(days=1)
        period_ends = days
        chart_labels = [d.strftime("%Y-%m-%d") for d in days]
        chart_title = f"Historico ({start_date:%Y-%m-%d} a {end_date:%Y-%m-%d})"
    else:
        month_starts = []
        current = date(start_date.year, start_date.month, 1)
        end_month = date(end_date.year, end_date.month, 1)
        while current <= end_month:
            month_starts.append(current)
            current = shift_months(current, 1)
        period_ends = [month_window(m.year, m.month).period_end for m in month_starts]
        chart_labels = [m.strftime("%Y-%m") for m in month_starts]
        chart_title = f"Historico ({month_starts[0]:%Y-%m} a {end_month:%Y-%m})"

    results = PerformanceIndicatorResult.objects.filter(
        indicator=indicator,
        plant=plant,
        frequency=frequency,
        period_end__gte=period_ends[0],
        period_end__lte=period_ends[-1],
    )
    if not results.exists():
        with transaction.atomic():
            for period_end in period_ends:
                if frequency == PerformanceIndicatorResult.FREQ_DAILY:
                    w = MonthWindow(period_end, period_end)
                else:
                    w = month_window(period_end.year, period_end.month)
                value, status, trace = compute_indicator(indicator, w)
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
        results = PerformanceIndicatorResult.objects.filter(
            indicator=indicator,
            plant=plant,
            frequency=frequency,
            period_end__gte=period_ends[0],
            period_end__lte=period_ends[-1],
        )
    result_map = {r.period_end: r for r in results}

    chart_values: list[float | None] = []
    for period_end in period_ends:
        res = result_map.get(period_end)
        if res and res.status == PerformanceIndicatorResult.STATUS_SUCCESS:
            chart_values.append(res.numeric_value)
        else:
            chart_values.append(None)

    context = {
        "plant": plant,
        "date_start": start_date.strftime("%Y-%m-%d"),
        "date_end": end_date.strftime("%Y-%m-%d"),
        "frequency": frequency,
        "indicator": indicator,
        "page_title": "Desempeno - KCL",
        "page_subtitle": "Formula 9: Rendimiento de Produccion de KCL (%)",
        "formula_equation": "R_kcl(m) = (Q_kcl(m) / Q_mp(m)) * 100",
        "formula_notes": [
            "R_kcl(m): rendimiento mensual (%) de produccion de KCL.",
            "Q_kcl(m): cantidad total de KCL producida en el mes m (TM).",
            "Q_mp(m): materia prima alimentada en el mes m (TM, base seca).",
        ],
        "variable_blocks": [
            {
                "variable": v,
                "form": forms[v.key],
            }
            for v in variables
        ],
        "can_save_mappings": can_save_mappings,
        "chart_title": chart_title,
        "chart_labels_json": json.dumps(chart_labels),
        "chart_values_json": json.dumps(chart_values),
    }
    return render(request, "performance/formulas.html", context)
