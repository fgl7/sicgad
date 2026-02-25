from __future__ import annotations

from datetime import date, timedelta
import re

from django.contrib import messages
from django.db.models import Max, Min
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

import json

from audit.utils import record_action

from accounts.decorators import admin_required
from ingest.models import PublishedDataPoint
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
from performance.services import compute_store_and_materialize_indicator
from schemas.models import ColumnDef, DatasetType
from structure.models import Entity


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


_EXPR_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[()+\-*/]")


def _tokenize_expression_text(raw: str | None) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    compact = text.replace(" ", "")
    tokens = _EXPR_TOKEN_RE.findall(compact)
    if "".join(tokens) != compact:
        return []
    return tokens


def _alpha_token(index_zero_based: int) -> str:
    # 0 -> A, 25 -> Z, 26 -> AA
    n = int(index_zero_based)
    token = ""
    while True:
        n, rem = divmod(n, 26)
        token = chr(65 + rem) + token
        if n == 0:
            break
        n -= 1
    return token


def _next_alias_token(existing_tokens: set[str]) -> str:
    normalized = {str(t).upper() for t in existing_tokens}
    idx = 0
    while True:
        candidate = _alpha_token(idx)
        if candidate not in normalized:
            return candidate
        idx += 1


def _build_indicator_key(entity: Entity, label: str) -> str:
    base = slugify(f"{entity.code}-{label}")[:70].strip("-")
    if not base:
        base = slugify(entity.code)[:20] or "formula"
    key = base
    counter = 1
    while PerformanceIndicator.objects.filter(key=key).exists():
        counter += 1
        suffix = f"-{counter}"
        key = f"{base[: max(1, 80 - len(suffix))]}{suffix}"
    return key


def _mark_indicator_draft(indicator: PerformanceIndicator) -> None:
    update_fields: list[str] = []
    if indicator.status != PerformanceIndicator.STATUS_DRAFT:
        indicator.status = PerformanceIndicator.STATUS_DRAFT
        update_fields.append("status")
    if indicator.approved_at is not None:
        indicator.approved_at = None
        update_fields.append("approved_at")
    if indicator.approved_by_id is not None:
        indicator.approved_by = None
        update_fields.append("approved_by")
    if update_fields:
        update_fields.append("updated_at")
        indicator.save(update_fields=update_fields)



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
    entity: Entity,
    window,
    stage: str,
    frequency: str,
    value: float | None,
    status: str,
    trace: dict,
) -> PerformanceIndicatorResult:
    result, _ = PerformanceIndicatorResult.objects.update_or_create(
        indicator=indicator,
        entity=entity,
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
    entities = Entity.objects.filter(is_active=True).order_by("code", "name")
    if not entities.exists():
        messages.error(request, "No existen entidades registradas.")
        return redirect("home")
    entity_id = request.POST.get("entity_id") or request.GET.get("entity_id")
    entity = Entity.objects.filter(id=entity_id).first() if entity_id else entities.first()
    if not entity:
        messages.error(request, "No existe la entidad seleccionada.")
        return redirect("home")
    formulas_qs = PerformanceIndicator.objects.filter(entity=entity, is_active=True).order_by("label")
    formula_id = request.POST.get("formula_id") if request.method == "POST" else request.GET.get("formula_id")
    if formula_id is None:
        formula_id = request.GET.get("formula_id")
    if formula_id == "":
        indicator = None
    else:
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
            key = _build_indicator_key(entity, label)
            indicator = PerformanceIndicator.objects.create(
                key=key,
                entity=entity,
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
                object_repr=f"{entity.code}:{indicator.key}",
                details="Formula creada desde UI",
            )
            messages.success(request, "Formula creada.")
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id if indicator else ''}"
        )
    if not indicator:
        indicator = None
    if action == "update_formula" and indicator:
        label = (request.POST.get("label") or "").strip()
        description = (
            (request.POST.get("description") or "").strip()
            if "description" in request.POST
            else indicator.description
        )
        unit = (
            (request.POST.get("unit") or "").strip()
            if "unit" in request.POST
            else indicator.unit
        )
        frequency = (
            _parse_frequency(request.POST.get("frequency"))
            if "frequency" in request.POST
            else indicator.frequency
        )
        if label:
            indicator.label = label
        indicator.description = description
        indicator.formula_text = description
        indicator.unit = unit
        indicator.frequency = frequency
        indicator.save(update_fields=["label", "description", "formula_text", "unit", "frequency", "updated_at"])
        _mark_indicator_draft(indicator)
        record_action(
            "OTHER",
            request=request,
            module="performance",
            object_repr=f"{entity.code}:{indicator.key}",
            details="Formula actualizada desde UI",
        )
        messages.success(request, "Formula actualizada.")
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "add_input" and indicator:
        column_id = request.POST.get("column_id")
        column = ColumnDef.objects.filter(
            id=column_id,
            dataset_type__entity=entity,
            dataset_type__status=DatasetType.STATUS_APPROVED,
            dataset_type__is_active=True,
            is_active=True,
        ).select_related("dataset_type").first()
        if not column:
            messages.error(request, "Seleccione una columna valida.")
        else:
            existing_tokens = set(indicator.inputs.filter(is_active=True).values_list("token", flat=True))
            token = _next_alias_token(existing_tokens)
            PerformanceIndicatorInput.objects.create(
                indicator=indicator,
                token=token,
                column=column,
                label=column.label,
            )
            _mark_indicator_draft(indicator)
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{entity.code}:{indicator.key}",
                details=f"Variable agregada: {token} -> {column.name}",
            )
            messages.success(request, "Variable agregada.")
            recalculate = True
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "remove_input" and indicator:
        input_id = request.POST.get("input_id")
        input_obj = indicator.inputs.filter(id=input_id).first()
        if input_obj:
            input_obj.delete()
            _mark_indicator_draft(indicator)
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{entity.code}:{indicator.key}",
                details=f"Variable eliminada: {input_obj.token}",
            )
            messages.success(request, "Variable eliminada.")
            recalculate = True
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}&recalculate=1"
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
                    dataset_type__entity=entity,
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
            try:
                inp.transform_value = float(transform_value_raw) if transform_value_raw else None
                inp.offset_periods = int(offset_raw) if offset_raw else 0
            except ValueError:
                messages.error(request, "Valores numericos invalidos en transformacion u offset.")
                return redirect(
                    f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}&recalculate=1"
                )
            inp.save(
                update_fields=["column", "aggregation", "transform", "transform_value", "offset_periods", "updated_at"]
            )
            _mark_indicator_draft(indicator)
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{entity.code}:{indicator.key}",
                details=f"Variable actualizada: {inp.token}",
            )
            messages.success(request, "Variable actualizada.")
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "save_formula" and indicator:
        manual_expression = (request.POST.get("expression_manual") or "").strip()
        manual_expression_rhs = manual_expression.split("=", 1)[1].strip() if "=" in manual_expression else manual_expression
        tokens = (
            _tokenize_expression_text(manual_expression_rhs)
            if manual_expression
            else _parse_expression_tokens(request.POST.get("expression_tokens"))
        )
        inputs = list(indicator.inputs.filter(is_active=True).values_list("token", flat=True))
        allowed_tokens = set(inputs)
        allowed_ops = {"+", "-", "*", "/", "(", ")"}
        if manual_expression and not tokens:
            messages.error(request, "Formula invalida. Usa solo tokens (A, B, C...), numeros y operadores + - * / ( ).")
            return redirect(
                f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}&recalculate=1"
            )
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
                indicator.expression_text = manual_expression or " ".join(tokens)
                indicator.save(update_fields=["expression", "expression_text", "updated_at"])
                _mark_indicator_draft(indicator)
                record_action(
                    "OTHER",
                    request=request,
                    module="performance",
                    object_repr=f"{entity.code}:{indicator.key}",
                    details="Formula actualizada (expresion)",
                )
                messages.success(request, "Formula guardada.")
                recalculate = True
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}&recalculate=1"
        )
    if action == "approve_formula" and indicator:
        active_inputs = list(indicator.inputs.filter(is_active=True))
        if not active_inputs:
            messages.error(request, "La formula debe tener al menos una variable antes de aprobar.")
        elif not indicator.expression:
            messages.error(request, "La formula debe tener una expresion guardada antes de aprobar.")
        else:
            materialize_frequency = _parse_frequency(
                request.POST.get("materialize_frequency") or indicator.frequency
            )
            if materialize_frequency not in {FREQ_DAILY, FREQ_MONTHLY}:
                messages.error(
                    request,
                    "Por ahora la aprobacion/materializacion solo soporta frecuencias diaria o mensual.",
                )
            else:
                start_date, end_date = _get_date_range(
                    materialize_frequency,
                    request.POST.get("date_start"),
                    request.POST.get("date_end"),
                )
                periods_to_process, _, _ = _build_periods(materialize_frequency, start_date, end_date)
                indicator.status = PerformanceIndicator.STATUS_APPROVED
                indicator.approved_at = timezone.now()
                indicator.approved_by = request.user
                indicator.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])

                success_count = 0
                not_calculable_count = 0
                error_count = 0
                for period_start, period_end in periods_to_process:
                    result = compute_store_and_materialize_indicator(
                        indicator,
                        MonthWindow(period_start, period_end),
                        frequency=materialize_frequency,
                    )
                    if result.status == PerformanceIndicatorResult.STATUS_SUCCESS:
                        success_count += 1
                    elif result.status == PerformanceIndicatorResult.STATUS_NOT_CALCULABLE:
                        not_calculable_count += 1
                    else:
                        error_count += 1

                indicator.refresh_from_db(fields=[
                    "output_dataset_type_id",
                    "output_value_column_id",
                    "output_date_column_id",
                ])
                details = (
                    f"Formula aprobada y materializada ({materialize_frequency}) "
                    f"ok={success_count}, no_calculable={not_calculable_count}, error={error_count}"
                )
                if indicator.output_dataset_type_id:
                    details += f", dataset={indicator.output_dataset_type_id}"
                record_action(
                    "OTHER",
                    request=request,
                    module="performance",
                    object_repr=f"{entity.code}:{indicator.key}",
                    details=details,
                )
                dataset_msg = (
                    f" Dataset derivado ID {indicator.output_dataset_type_id} actualizado."
                    if indicator.output_dataset_type_id
                    else ""
                )
                messages.success(
                    request,
                    (
                        "Formula aprobada. "
                        f"Resultados: {success_count} exitosos, {not_calculable_count} no calculables, {error_count} con error."
                        + dataset_msg
                    ),
                )
        redirect_url = (
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}"
            f"&frequency={request.POST.get('materialize_frequency') or indicator.frequency}"
            f"&date_start={request.POST.get('date_start') or ''}"
            f"&date_end={request.POST.get('date_end') or ''}"
            "&recalculate=1"
        )
        return redirect(redirect_url)
    if action == "delete_formula" and indicator:
        deleted_label = indicator.label
        deleted_key = indicator.key
        indicator.is_active = False
        if indicator.status != PerformanceIndicator.STATUS_ARCHIVED:
            indicator.status = PerformanceIndicator.STATUS_ARCHIVED
            indicator.save(update_fields=["is_active", "status", "updated_at"])
        else:
            indicator.save(update_fields=["is_active", "updated_at"])
        record_action(
            "OTHER",
            request=request,
            module="performance",
            object_repr=f"{entity.code}:{deleted_key}",
            details="Formula archivada/eliminada desde UI (soft delete)",
        )
        messages.success(request, f"Formula '{deleted_label}' eliminada.")
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&frequency={request.POST.get('frequency') or FREQ_MONTHLY}"
            f"&date_start={request.POST.get('date_start') or ''}&date_end={request.POST.get('date_end') or ''}"
        )
    if action == "clear_formula" and indicator:
        indicator.inputs.all().delete()
        indicator.expression = []
        indicator.expression_text = ""
        indicator.description = ""
        indicator.formula_text = ""
        indicator.unit = ""
        indicator.save(update_fields=["expression", "expression_text", "description", "formula_text", "unit", "updated_at"])
        _mark_indicator_draft(indicator)
        record_action(
            "OTHER",
            request=request,
            module="performance",
            object_repr=f"{entity.code}:{indicator.key}",
            details="Formula limpiada desde UI (variables/expresion/campos auxiliares)",
        )
        messages.success(request, "Formula limpiada.")
        return redirect(
            f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}"
            f"&frequency={request.POST.get('frequency') or FREQ_MONTHLY}"
            f"&date_start={request.POST.get('date_start') or ''}&date_end={request.POST.get('date_end') or ''}"
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
    preview_rows: list[dict] = []
    if indicator and periods:
        period_ends = [p[1] for p in periods]
        results_qs = PerformanceIndicatorResult.objects.filter(
            indicator=indicator,
            entity=entity,
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
                    entity=entity,
                    window=w,
                    stage="DRAFT",
                    frequency=frequency,
                    value=value,
                    status=status,
                    trace=trace,
                )
            results_qs = PerformanceIndicatorResult.objects.filter(
                indicator=indicator,
                entity=entity,
                frequency=frequency,
                period_end__gte=period_ends[0],
                period_end__lte=period_ends[-1],
            )
            existing = {r.period_end: r for r in results_qs}
        for period_end in period_ends:
            res = existing.get(period_end)
            chart_values.append(res.numeric_value if res else None)
        for idx, period_end in enumerate(period_ends):
            res = existing.get(period_end)
            preview_rows.append(
                {
                    "label": chart_labels[idx] if idx < len(chart_labels) else period_end.strftime("%Y-%m-%d"),
                    "status": res.status if res else "NO_DATA",
                    "value": (res.numeric_value if res and res.status == PerformanceIndicatorResult.STATUS_SUCCESS else None),
                }
            )
    column_options = list(
        ColumnDef.objects.filter(
            dataset_type__entity=entity,
            dataset_type__status=DatasetType.STATUS_APPROVED,
            dataset_type__is_active=True,
            is_active=True,
        )
        .select_related("dataset_type")
        .order_by("dataset_type__name", "display_order", "label", "name")
    )
    published_points_qs = PublishedDataPoint.objects.filter(instance__entity=entity)
    published_range = published_points_qs.aggregate(
        min_period=Min("instance__period"),
        max_period=Max("instance__period"),
    )
    entity_published_frequencies = sorted(
        {
            f
            for f in published_points_qs.values_list(
                "instance__dataset_type__validation_frequency", flat=True
            ).distinct()
            if f
        }
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
        "entity": entity,
        "entities": list(entities),
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
        "preview_rows": preview_rows,
        "entity_published_min_period": published_range.get("min_period"),
        "entity_published_max_period": published_range.get("max_period"),
        "entity_published_frequencies": entity_published_frequencies,
    }
    return render(request, "performance/formulas.html", context)
