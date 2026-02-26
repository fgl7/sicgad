from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date, timedelta
import math
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.core.cache import cache
from django.db.models import Max, Min
from django.http import HttpRequest, HttpResponse, JsonResponse
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
from performance.services import (
    MonthWindow,
    compute_indicator,
    evaluate_expression,
    month_window,
    resolve_input_value,
    shift_period,
    shift_months,
)
from performance.services import compute_store_and_materialize_indicator
from schemas.models import ColumnDef, DatasetType
from structure.models import Entity

FORMULA_INPUT_COLUMN_TYPES = ("INTEGER", "FLOAT")
FORMULA_INPUT_SUPPORTED_FREQUENCIES = {FREQ_DAILY, FREQ_WEEKLY, FREQ_MONTHLY}


def _formula_builder_url(
    *,
    entity_id: int,
    formula_id: int | str | None = None,
    frequency: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    recalculate: bool = False,
    new_formula: bool = False,
) -> str:
    params: dict[str, str | int] = {"entity_id": entity_id}
    if formula_id is not None:
        params["formula_id"] = formula_id
    if frequency:
        params["frequency"] = frequency
    if date_start:
        params["date_start"] = date_start
    if date_end:
        params["date_end"] = date_end
    if recalculate:
        params["recalculate"] = "1"
    if new_formula:
        params["new_formula"] = "1"
    return f"/performance/formulas/?{urlencode(params)}"


def _wants_json_response(request: HttpRequest) -> bool:
    requested_with = (request.headers.get("X-Requested-With") or "").lower()
    accept = (request.headers.get("Accept") or "").lower()
    return requested_with == "xmlhttprequest" or "application/json" in accept


def _formula_approve_progress_key(user_id: int, formula_id: int) -> str:
    return f"performance:formula-approve-progress:v1:u{user_id}:f{formula_id}"


def _set_formula_approve_progress(
    *,
    user_id: int,
    formula_id: int,
    status: str,
    percent: int,
    message: str,
    stage_index: int | None = None,
    stage_total: int | None = None,
    stage_label: str = "",
    timeout: int = 60 * 10,
) -> None:
    payload = {
        "ok": True,
        "status": status,
        "percent": max(0, min(100, int(percent))),
        "message": message or "",
        "stage_index": stage_index,
        "stage_total": stage_total,
        "stage_label": stage_label or "",
    }
    cache.set(_formula_approve_progress_key(user_id, formula_id), payload, timeout=timeout)


def _get_formula_approve_progress(user_id: int, formula_id: int):
    return cache.get(_formula_approve_progress_key(user_id, formula_id))


def _column_formula_frequency(column: ColumnDef) -> str | None:
    raw = str(getattr(column.dataset_type, "validation_frequency", "") or "").strip().upper()
    if raw in FORMULA_INPUT_SUPPORTED_FREQUENCIES:
        return raw
    return None


def _validate_input_columns_frequency(columns: list[ColumnDef]) -> tuple[str | None, str | None]:
    if not columns:
        return None, None
    normalized: set[str] = set()
    unsupported: list[str] = []
    for col in columns:
        freq = _column_formula_frequency(col)
        if not freq:
            ds = getattr(col, "dataset_type", None)
            raw = str(getattr(ds, "validation_frequency", "") or "N/D")
            ds_name = getattr(ds, "name", "schema")
            unsupported.append(f"{col.label or col.name} [{ds_name}: {raw}]")
            continue
        normalized.add(freq)
    if unsupported:
        return None, (
            "Las formulas solo soportan columnas de esquemas con periodicidad DAILY, WEEKLY o MONTHLY. "
            f"Columnas no soportadas: {', '.join(unsupported)}."
        )
    if len(normalized) > 1:
        return None, (
            "Todas las variables de la formula deben pertenecer a esquemas de la misma periodicidad. "
            f"Periodicidades detectadas: {', '.join(sorted(normalized))}."
        )
    return next(iter(normalized)), None


def _filter_periods_with_complete_inputs(
    *,
    indicator: PerformanceIndicator,
    inputs: list[PerformanceIndicatorInput],
    periods: list[tuple[date, date]],
    labels: list[str],
    frequency: str,
) -> tuple[list[tuple[date, date]], list[str], int]:
    if not inputs or not periods:
        return periods, labels, 0

    filtered_periods: list[tuple[date, date]] = []
    filtered_labels: list[str] = []
    skipped = 0
    for idx, (period_start, period_end) in enumerate(periods):
        window = MonthWindow(period_start, period_end)
        has_all_inputs = True
        for inp in inputs:
            val, _trace = resolve_input_value(inp, window, frequency=frequency)
            if val is None:
                has_all_inputs = False
                break
        if not has_all_inputs:
            skipped += 1
            continue
        filtered_periods.append((period_start, period_end))
        filtered_labels.append(labels[idx] if idx < len(labels) else period_end.strftime("%Y-%m-%d"))
    return filtered_periods, filtered_labels, skipped


def _derive_common_available_period_range(
    *,
    inputs: list[PerformanceIndicatorInput],
    frequency: str,
) -> tuple[date, date] | None:
    if not inputs:
        return None

    target_starts: list[date] = []
    target_ends: list[date] = []
    for inp in inputs:
        column = inp.column
        dataset_type = column.dataset_type
        bounds = PublishedDataPoint.objects.filter(
            instance__entity=inp.indicator.entity,
            instance__dataset_type=dataset_type,
            column=column,
            numeric_value__isnull=False,
        ).aggregate(
            min_period=Min("instance__period"),
            max_period=Max("instance__period"),
        )
        source_min = bounds.get("min_period")
        source_max = bounds.get("max_period")
        if source_min is None or source_max is None:
            return None

        # resolve_input_value() shifts source lookup by `offset_periods`; invert that shift to
        # estimate the target periods that can be computed from this variable.
        target_min = shift_period(source_min, frequency, -int(inp.offset_periods or 0))
        target_max = shift_period(source_max, frequency, -int(inp.offset_periods or 0))
        if target_min > target_max:
            target_min, target_max = target_max, target_min
        target_starts.append(target_min)
        target_ends.append(target_max)

    if not target_starts or not target_ends:
        return None

    start_date = max(target_starts)
    end_date = min(target_ends)
    if start_date > end_date:
        return None
    return start_date, end_date


def _sanitize_chart_values(values: list[float | None]) -> list[float | None]:
    safe: list[float | None] = []
    for value in values:
        if value is None:
            safe.append(None)
            continue
        try:
            num = float(value)
        except Exception:
            safe.append(None)
            continue
        safe.append(num if math.isfinite(num) else None)
    return safe


def _format_result_label(
    *,
    frequency: str,
    period_start: date | None,
    period_end: date,
) -> str:
    if frequency == FREQ_DAILY:
        return period_end.strftime("%Y-%m-%d")
    if frequency == FREQ_MONTHLY:
        return period_end.strftime("%Y-%m")
    if frequency == FREQ_YEARLY:
        return period_end.strftime("%Y")
    ref = period_start or period_end
    return ref.strftime("%Y-%m-%d")


def _prefetch_input_points_for_preview(
    *,
    inputs: list[PerformanceIndicatorInput],
    periods: list[tuple[date, date]],
    frequency: str,
) -> dict[int, dict]:
    data: dict[int, dict] = {}
    if not inputs or not periods:
        return data

    for inp in inputs:
        source_starts: list[date] = []
        source_ends: list[date] = []
        for period_start, period_end in periods:
            source_starts.append(shift_period(period_start, frequency, inp.offset_periods))
            source_ends.append(shift_period(period_end, frequency, inp.offset_periods))
        source_start = min(source_starts)
        source_end = max(source_ends)

        by_period: dict[date, list[tuple[float, int]]] = {}
        rows = (
            PublishedDataPoint.objects.filter(
                instance__entity=inp.indicator.entity,
                instance__dataset_type=inp.column.dataset_type,
                column=inp.column,
                instance__period__gte=source_start,
                instance__period__lte=source_end,
                numeric_value__isnull=False,
            )
            .order_by("instance__period", "id")
            .values_list("instance__period", "numeric_value", "id")
            .iterator(chunk_size=2000)
        )
        for period_value, numeric_value, point_id in rows:
            if period_value is None or numeric_value is None:
                continue
            by_period.setdefault(period_value, []).append((float(numeric_value), int(point_id)))

        data[inp.id] = {
            "by_period": by_period,
            "sorted_periods": sorted(by_period.keys()),
        }
    return data


def _resolve_prefetched_input_value(
    *,
    input_def: PerformanceIndicatorInput,
    window: MonthWindow,
    frequency: str,
    prefetched: dict[int, dict],
) -> tuple[float | None, dict]:
    grouped = prefetched.get(input_def.id) or {}
    by_period: dict[date, list[tuple[float, int]]] = grouped.get("by_period") or {}
    sorted_periods: list[date] = grouped.get("sorted_periods") or []

    shifted_start = shift_period(window.period_start, frequency, input_def.offset_periods)
    shifted_end = shift_period(window.period_end, frequency, input_def.offset_periods)
    if shifted_start > shifted_end:
        shifted_start, shifted_end = shifted_end, shifted_start

    left = bisect_left(sorted_periods, shifted_start)
    right = bisect_right(sorted_periods, shifted_end)
    period_slice = sorted_periods[left:right]

    trace: dict = {
        "token": input_def.token,
        "column": input_def.column.name,
        "dataset": input_def.column.dataset_type.slug,
        "aggregation": input_def.aggregation,
        "window_used": [shifted_start.isoformat(), shifted_end.isoformat()],
        "source": "prefetched",
    }

    agg = (input_def.aggregation or "SUM").upper()
    value: float | None = None

    if agg == "LAST":
        last_value: float | None = None
        for period_key in period_slice:
            bucket = by_period.get(period_key) or []
            if bucket:
                last_value = float(bucket[-1][0])
        value = last_value
    else:
        flat_values: list[float] = []
        for period_key in period_slice:
            bucket = by_period.get(period_key) or []
            for numeric_value, _point_id in bucket:
                flat_values.append(float(numeric_value))

        if agg == "SUM":
            value = float(sum(flat_values)) if flat_values else None
        elif agg == "AVG":
            value = (float(sum(flat_values)) / len(flat_values)) if flat_values else None
        elif agg == "MAX":
            value = max(flat_values) if flat_values else None
        elif agg == "MIN":
            value = min(flat_values) if flat_values else None
        elif agg == "NONE":
            if len(flat_values) == 1:
                value = float(flat_values[0])
            else:
                trace["error"] = f"NONE requiere 1 valor; se encontraron {len(flat_values)}"
                value = None
        else:
            trace["error"] = f"Aggregation no soportada: {agg}"
            value = None

    if value is None:
        return None, trace

    transform = (input_def.transform or "NONE").upper()
    if transform == "MULTIPLY":
        if input_def.transform_value is None:
            trace["error"] = "transform MULTIPLY requiere transform_value"
            return None, trace
        value = float(value) * float(input_def.transform_value)
    elif transform == "ADD":
        if input_def.transform_value is None:
            trace["error"] = "transform ADD requiere transform_value"
            return None, trace
        value = float(value) + float(input_def.transform_value)
    elif transform != "NONE":
        trace["error"] = f"Transform no soportada: {transform}"
        return None, trace

    trace.update(
        {
            "transform": transform,
            "transform_value": input_def.transform_value,
            "value": float(value),
        }
    )
    return float(value), trace


def _bulk_upsert_indicator_results(
    *,
    indicator: PerformanceIndicator,
    entity: Entity,
    frequency: str,
    rows: list[dict],
) -> None:
    if not rows:
        return

    period_ends = [row["period_end"] for row in rows]
    existing_map = {
        r.period_end: r
        for r in PerformanceIndicatorResult.objects.filter(
            indicator=indicator,
            entity=entity,
            frequency=frequency,
            period_end__in=period_ends,
        )
    }
    now_dt = timezone.now()
    to_create: list[PerformanceIndicatorResult] = []
    to_update: list[PerformanceIndicatorResult] = []

    for row in rows:
        existing = existing_map.get(row["period_end"])
        if existing:
            existing.period_start = row["period_start"]
            existing.stage = "DRAFT"
            existing.status = row["status"]
            existing.numeric_value = row["value"]
            existing.text_value = ""
            existing.trace = row["trace"]
            existing.computed_at = now_dt
            to_update.append(existing)
        else:
            to_create.append(
                PerformanceIndicatorResult(
                    indicator=indicator,
                    entity=entity,
                    period_start=row["period_start"],
                    period_end=row["period_end"],
                    frequency=frequency,
                    stage="DRAFT",
                    status=row["status"],
                    numeric_value=row["value"],
                    text_value="",
                    trace=row["trace"],
                    computed_at=now_dt,
                )
            )

    if to_create:
        PerformanceIndicatorResult.objects.bulk_create(to_create, batch_size=500)
    if to_update:
        PerformanceIndicatorResult.objects.bulk_update(
            to_update,
            fields=["period_start", "stage", "status", "numeric_value", "text_value", "trace", "computed_at"],
            batch_size=500,
        )


def _compute_expression_preview_fast(
    *,
    indicator: PerformanceIndicator,
    entity: Entity,
    inputs: list[PerformanceIndicatorInput],
    periods: list[tuple[date, date]],
    labels: list[str],
    frequency: str,
) -> dict:
    prefetched = _prefetch_input_points_for_preview(inputs=inputs, periods=periods, frequency=frequency)
    expr_tokens = [str(t) for t in (indicator.expression or [])]

    out_labels: list[str] = []
    out_values: list[float | None] = []
    preview_rows: list[dict] = []
    upsert_rows: list[dict] = []
    skipped_no_common_data = 0

    for idx, (period_start, period_end) in enumerate(periods):
        window = MonthWindow(period_start, period_end)
        value_map: dict[str, float] = {}
        input_traces: dict[str, dict] = {}
        missing_input = False
        for inp in inputs:
            val, trace = _resolve_prefetched_input_value(
                input_def=inp,
                window=window,
                frequency=frequency,
                prefetched=prefetched,
            )
            input_traces[inp.token] = trace
            if val is None:
                missing_input = True
                break
            value_map[inp.token] = float(val)
        if missing_input:
            skipped_no_common_data += 1
            continue

        calc_value, err = evaluate_expression(expr_tokens, value_map)
        if err:
            status = (
                PerformanceIndicatorResult.STATUS_NOT_CALCULABLE
                if err == "división por cero" or err == "divisiÃ³n por cero"
                else PerformanceIndicatorResult.STATUS_ERROR
            )
            numeric_value = None
            trace = {"inputs": input_traces, "expression": expr_tokens, "error": err, "source": "fast_preview"}
        else:
            status = PerformanceIndicatorResult.STATUS_SUCCESS
            numeric_value = float(calc_value) if calc_value is not None else None
            trace = {"inputs": input_traces, "expression": expr_tokens, "source": "fast_preview"}

        label = labels[idx] if idx < len(labels) else _format_result_label(
            frequency=frequency,
            period_start=period_start,
            period_end=period_end,
        )
        out_labels.append(label)
        out_values.append(numeric_value if status == PerformanceIndicatorResult.STATUS_SUCCESS else None)
        preview_rows.append(
            {
                "label": label,
                "status": status,
                "value": (numeric_value if status == PerformanceIndicatorResult.STATUS_SUCCESS else None),
            }
        )
        upsert_rows.append(
            {
                "period_start": period_start,
                "period_end": period_end,
                "status": status,
                "value": numeric_value,
                "trace": trace,
            }
        )

    _bulk_upsert_indicator_results(
        indicator=indicator,
        entity=entity,
        frequency=frequency,
        rows=upsert_rows,
    )
    return {
        "chart_labels": out_labels,
        "chart_values": out_values,
        "preview_rows": preview_rows,
        "preview_common_periods_count": len(out_labels),
        "preview_skipped_no_common_data": skipped_no_common_data,
    }


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
def formula_approve_progress(request: HttpRequest, formula_id: int) -> HttpResponse:
    indicator = PerformanceIndicator.objects.filter(id=formula_id).only("id").first()
    if not indicator:
        return JsonResponse({"ok": False, "error": "Formula no encontrada."}, status=404)
    payload = _get_formula_approve_progress(request.user.id, indicator.id) or {
        "ok": True,
        "status": "PENDING",
        "percent": 0,
        "message": "Esperando inicio de aprobacion...",
        "stage_index": None,
        "stage_total": None,
        "stage_label": "",
    }
    return JsonResponse(payload)


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
    force_new_formula = request.method == "GET" and request.GET.get("new_formula") == "1"
    formula_id = request.POST.get("formula_id") if request.method == "POST" else request.GET.get("formula_id")
    if formula_id is None:
        formula_id = request.GET.get("formula_id")
    if force_new_formula:
        formula_id = ""
    if formula_id == "":
        indicator = None
    elif formula_id:
        indicator = formulas_qs.filter(id=formula_id).first() if formula_id else formulas_qs.first()
    elif request.method == "GET":
        # Avoid auto-loading the first formula on initial entry: it can trigger heavy preview
        # recomputation and slows down the module landing page.
        indicator = None
    else:
        indicator = formulas_qs.first()
    action = request.POST.get("action") if request.method == "POST" else None
    recalculate = request.GET.get("recalculate") == "1"
    ui_frequency = request.POST.get("frequency") or request.GET.get("frequency")
    ui_date_start = request.POST.get("date_start") or request.GET.get("date_start")
    ui_date_end = request.POST.get("date_end") or request.GET.get("date_end")
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
            _formula_builder_url(
                entity_id=entity.id,
                formula_id=indicator.id if indicator else "",
                frequency=ui_frequency,
                date_start=ui_date_start,
                date_end=ui_date_end,
            )
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
            _formula_builder_url(
                entity_id=entity.id,
                formula_id=indicator.id,
                frequency=ui_frequency,
                date_start=ui_date_start,
                date_end=ui_date_end,
                recalculate=True,
            )
        )
    if action == "add_input" and indicator:
        column_id = request.POST.get("column_id")
        column = ColumnDef.objects.filter(
            id=column_id,
            dataset_type__entity=entity,
            dataset_type__status=DatasetType.STATUS_APPROVED,
            dataset_type__is_active=True,
            data_type__in=FORMULA_INPUT_COLUMN_TYPES,
            is_active=True,
        ).select_related("dataset_type").first()
        if not column:
            messages.error(request, "Seleccione una columna valida.")
        else:
            existing_inputs = list(
                indicator.inputs.filter(is_active=True)
                .select_related("column", "column__dataset_type")
                .order_by("token")
            )
            common_input_frequency, freq_error = _validate_input_columns_frequency(
                [inp.column for inp in existing_inputs] + [column]
            )
            if freq_error:
                messages.error(request, freq_error)
                return redirect(
                    _formula_builder_url(
                        entity_id=entity.id,
                        formula_id=indicator.id,
                        frequency=ui_frequency,
                        date_start=ui_date_start,
                        date_end=ui_date_end,
                        recalculate=True,
                    )
                )
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
            if common_input_frequency and indicator.frequency != common_input_frequency:
                indicator.frequency = common_input_frequency
                indicator.save(update_fields=["frequency", "updated_at"])
            messages.success(request, "Variable agregada.")
        return redirect(
            _formula_builder_url(
                entity_id=entity.id,
                formula_id=indicator.id,
                frequency=(common_input_frequency if 'common_input_frequency' in locals() and common_input_frequency else ui_frequency),
                date_start=ui_date_start,
                date_end=ui_date_end,
                recalculate=bool(indicator.expression),
            )
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
        return redirect(
            _formula_builder_url(
                entity_id=entity.id,
                formula_id=indicator.id,
                frequency=ui_frequency,
                date_start=ui_date_start,
                date_end=ui_date_end,
                recalculate=bool(indicator.expression),
            )
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
                    data_type__in=FORMULA_INPUT_COLUMN_TYPES,
                    is_active=True,
                )
                .select_related("dataset_type")
                .first()
                if column_id
                else inp.column
            )
            siblings = list(
                indicator.inputs.filter(is_active=True)
                .exclude(id=inp.id)
                .select_related("column", "column__dataset_type")
                .order_by("token")
            )
            candidate_column = column or inp.column
            common_input_frequency, freq_error = _validate_input_columns_frequency(
                [s.column for s in siblings] + ([candidate_column] if candidate_column else [])
            )
            if freq_error:
                messages.error(request, freq_error)
                return redirect(
                    _formula_builder_url(
                        entity_id=entity.id,
                        formula_id=indicator.id,
                        frequency=ui_frequency,
                        date_start=ui_date_start,
                        date_end=ui_date_end,
                        recalculate=True,
                    )
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
                    _formula_builder_url(
                        entity_id=entity.id,
                        formula_id=indicator.id,
                        frequency=ui_frequency,
                        date_start=ui_date_start,
                        date_end=ui_date_end,
                        recalculate=True,
                    )
                )
            inp.save(
                update_fields=["column", "aggregation", "transform", "transform_value", "offset_periods", "updated_at"]
            )
            _mark_indicator_draft(indicator)
            if common_input_frequency and indicator.frequency != common_input_frequency:
                indicator.frequency = common_input_frequency
                indicator.save(update_fields=["frequency", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="performance",
                object_repr=f"{entity.code}:{indicator.key}",
                details=f"Variable actualizada: {inp.token}",
            )
            messages.success(request, "Variable actualizada.")
        return redirect(
            _formula_builder_url(
                entity_id=entity.id,
                formula_id=indicator.id,
                frequency=(common_input_frequency if 'common_input_frequency' in locals() and common_input_frequency else ui_frequency),
                date_start=ui_date_start,
                date_end=ui_date_end,
                recalculate=bool(indicator.expression),
            )
        )
    if action == "save_formula" and indicator:
        active_inputs = list(
            indicator.inputs.filter(is_active=True)
            .select_related("column", "column__dataset_type")
            .order_by("token")
        )
        common_input_frequency, freq_error = _validate_input_columns_frequency(
            [inp.column for inp in active_inputs]
        )
        if freq_error:
            messages.error(request, freq_error)
            return redirect(
                _formula_builder_url(
                    entity_id=entity.id,
                    formula_id=indicator.id,
                    frequency=ui_frequency,
                    date_start=ui_date_start,
                    date_end=ui_date_end,
                    recalculate=True,
                )
            )
        manual_expression = (request.POST.get("expression_manual") or "").strip()
        manual_expression_rhs = manual_expression.split("=", 1)[1].strip() if "=" in manual_expression else manual_expression
        tokens = (
            _tokenize_expression_text(manual_expression_rhs)
            if manual_expression
            else _parse_expression_tokens(request.POST.get("expression_tokens"))
        )
        allowed_tokens = {inp.token for inp in active_inputs}
        allowed_ops = {"+", "-", "*", "/", "(", ")"}
        if manual_expression and not tokens:
            messages.error(request, "Formula invalida. Usa solo tokens (A, B, C...), numeros y operadores + - * / ( ).")
            return redirect(
                _formula_builder_url(
                    entity_id=entity.id,
                    formula_id=indicator.id,
                    frequency=ui_frequency,
                    date_start=ui_date_start,
                    date_end=ui_date_end,
                    recalculate=True,
                )
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
                update_fields = ["expression", "expression_text", "updated_at"]
                if common_input_frequency and indicator.frequency != common_input_frequency:
                    indicator.frequency = common_input_frequency
                    update_fields.append("frequency")
                indicator.save(update_fields=update_fields)
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
            _formula_builder_url(
                entity_id=entity.id,
                formula_id=indicator.id,
                frequency=(common_input_frequency if common_input_frequency else ui_frequency),
                date_start=ui_date_start,
                date_end=ui_date_end,
                recalculate=True,
            )
        )
    if action == "approve_formula" and indicator:
        wants_json = _wants_json_response(request)
        approval_succeeded = False
        _set_formula_approve_progress(
            user_id=request.user.id,
            formula_id=indicator.id,
            status="RUNNING",
            percent=2,
            message="Preparando aprobacion de formula...",
            stage_index=1,
            stage_total=4,
            stage_label="Preparacion",
        )
        active_inputs = list(
            indicator.inputs.filter(is_active=True)
            .select_related("column", "column__dataset_type")
            .order_by("token")
        )
        common_input_frequency, freq_error = _validate_input_columns_frequency(
            [inp.column for inp in active_inputs]
        )
        if not active_inputs:
            messages.error(request, "La formula debe tener al menos una variable antes de aprobar.")
            _set_formula_approve_progress(
                user_id=request.user.id,
                formula_id=indicator.id,
                status="FAILED",
                percent=100,
                message="La formula no tiene variables configuradas.",
                stage_index=4,
                stage_total=4,
                stage_label="Error",
            )
        elif freq_error:
            messages.error(request, freq_error)
            _set_formula_approve_progress(
                user_id=request.user.id,
                formula_id=indicator.id,
                status="FAILED",
                percent=100,
                message=freq_error,
                stage_index=4,
                stage_total=4,
                stage_label="Error",
            )
        elif not indicator.expression:
            messages.error(request, "La formula debe tener una expresion guardada antes de aprobar.")
            _set_formula_approve_progress(
                user_id=request.user.id,
                formula_id=indicator.id,
                status="FAILED",
                percent=100,
                message="La formula no tiene expresion guardada.",
                stage_index=4,
                stage_total=4,
                stage_label="Error",
            )
        else:
            _set_formula_approve_progress(
                user_id=request.user.id,
                formula_id=indicator.id,
                status="RUNNING",
                percent=10,
                message="Validando configuracion y frecuencia de materializacion...",
                stage_index=2,
                stage_total=4,
                stage_label="Validacion",
            )
            requested_materialize_frequency = _parse_frequency(
                request.POST.get("materialize_frequency") or indicator.frequency
            )
            materialize_frequency = common_input_frequency or requested_materialize_frequency
            if (
                common_input_frequency
                and requested_materialize_frequency != common_input_frequency
            ):
                messages.warning(
                    request,
                    f"Se ajusto la frecuencia de materializacion a {common_input_frequency} para coincidir con la periodicidad de las variables.",
                )
            if materialize_frequency not in {FREQ_DAILY, FREQ_MONTHLY}:
                messages.error(
                    request,
                    "Por ahora la aprobacion/materializacion solo soporta frecuencias diaria o mensual.",
                )
                _set_formula_approve_progress(
                    user_id=request.user.id,
                    formula_id=indicator.id,
                    status="FAILED",
                    percent=100,
                    message="Frecuencia no soportada para materializacion (solo DAILY/MONTHLY).",
                    stage_index=4,
                    stage_total=4,
                    stage_label="Error",
                )
            else:
                common_available_range = _derive_common_available_period_range(
                    inputs=active_inputs,
                    frequency=materialize_frequency,
                )
                if common_available_range:
                    start_date, end_date = common_available_range
                else:
                    start_date, end_date = _get_date_range(
                        materialize_frequency,
                        request.POST.get("date_start"),
                        request.POST.get("date_end"),
                    )
                periods_to_process, period_labels, _ = _build_periods(materialize_frequency, start_date, end_date)
                periods_to_process, _period_labels, skipped_no_common_data = _filter_periods_with_complete_inputs(
                    indicator=indicator,
                    inputs=active_inputs,
                    periods=periods_to_process,
                    labels=period_labels,
                    frequency=materialize_frequency,
                )
                total_periods_to_process = len(periods_to_process)
                _set_formula_approve_progress(
                    user_id=request.user.id,
                    formula_id=indicator.id,
                    status="RUNNING",
                    percent=18,
                    message=(
                        f"Procesando {total_periods_to_process} periodos"
                        + (f" (omitidos {skipped_no_common_data} sin solapamiento)." if skipped_no_common_data else ".")
                    ),
                    stage_index=3,
                    stage_total=4,
                    stage_label="Calculo y materializacion",
                )
                indicator.status = PerformanceIndicator.STATUS_APPROVED
                indicator.approved_at = timezone.now()
                indicator.approved_by = request.user
                indicator.frequency = materialize_frequency
                indicator.save(update_fields=["status", "approved_at", "approved_by", "frequency", "updated_at"])

                success_count = 0
                not_calculable_count = 0
                error_count = 0
                for idx, (period_start, period_end) in enumerate(periods_to_process, start=1):
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
                    if total_periods_to_process:
                        progress_percent = 18 + int((idx / total_periods_to_process) * 74)
                        _set_formula_approve_progress(
                            user_id=request.user.id,
                            formula_id=indicator.id,
                            status="RUNNING",
                            percent=progress_percent,
                            message=(
                                f"Procesando periodo {idx}/{total_periods_to_process}. "
                                f"ok={success_count}, no_calculable={not_calculable_count}, error={error_count}"
                            ),
                            stage_index=3,
                            stage_total=4,
                            stage_label="Calculo y materializacion",
                        )

                indicator.refresh_from_db(fields=[
                    "output_dataset_type_id",
                    "output_value_column_id",
                    "output_date_column_id",
                ])
                details = (
                    f"Formula aprobada y materializada ({materialize_frequency}) "
                    f"ok={success_count}, no_calculable={not_calculable_count}, error={error_count}"
                )
                if skipped_no_common_data:
                    details += f", skipped_no_common_data={skipped_no_common_data}"
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
                        + (
                            f" Se omitieron {skipped_no_common_data} periodos sin datos completos en todas las variables."
                            if skipped_no_common_data
                            else ""
                        )
                        + dataset_msg
                    ),
                )
                approval_succeeded = True
                _set_formula_approve_progress(
                    user_id=request.user.id,
                    formula_id=indicator.id,
                    status="DONE",
                    percent=100,
                    message=(
                        f"Aprobacion completada. ok={success_count}, no_calculable={not_calculable_count}, error={error_count}"
                    ),
                    stage_index=4,
                    stage_total=4,
                    stage_label="Completado",
                )
        if approval_succeeded:
            redirect_url = _formula_builder_url(
                entity_id=entity.id,
                new_formula=True,
            )
        else:
            redirect_url = (
                f"/performance/formulas/?entity_id={entity.id}&formula_id={indicator.id}"
                f"&frequency={request.POST.get('materialize_frequency') or indicator.frequency}"
                f"&date_start={request.POST.get('date_start') or ''}"
                f"&date_end={request.POST.get('date_end') or ''}"
                "&recalculate=1"
            )
        if wants_json:
            return JsonResponse(
                {
                    "ok": True,
                    "redirect_url": redirect_url,
                    "message": "Aprobacion procesada. Redirigiendo...",
                    "stage_index": 4,
                    "stage_total": 4,
                    "stage_label": "Completado",
                }
            )
        return redirect(redirect_url)
    if action == "delete_formula" and indicator:
        deleted_label = indicator.label
        deleted_key = indicator.key
        derived_dataset = indicator.output_dataset_type
        deactivated_derived_dataset = False
        indicator.is_active = False
        if indicator.status != PerformanceIndicator.STATUS_ARCHIVED:
            indicator.status = PerformanceIndicator.STATUS_ARCHIVED
            indicator.save(update_fields=["is_active", "status", "updated_at"])
        else:
            indicator.save(update_fields=["is_active", "updated_at"])

        if derived_dataset:
            has_other_active_indicators = (
                derived_dataset.derived_performance_indicators.filter(is_active=True)
                .exclude(id=indicator.id)
                .exists()
            )
            if not has_other_active_indicators:
                dataset_changed_fields: list[str] = []
                if derived_dataset.is_active:
                    derived_dataset.is_active = False
                    dataset_changed_fields.append("is_active")
                if dataset_changed_fields:
                    dataset_changed_fields.append("updated_at")
                    derived_dataset.save(update_fields=dataset_changed_fields)
                    deactivated_derived_dataset = True
                derived_dataset.columns.filter(id__in=[
                    indicator.output_date_column_id,
                    indicator.output_value_column_id,
                ]).update(is_active=False)

        delete_details = "Formula archivada/eliminada desde UI (soft delete)"
        if deactivated_derived_dataset and derived_dataset:
            delete_details += f"; dataset derivado desactivado (id={derived_dataset.id})"
        record_action(
            "OTHER",
            request=request,
            module="performance",
            object_repr=f"{entity.code}:{deleted_key}",
            details=delete_details,
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
    inputs = (
        list(
            indicator.inputs.filter(is_active=True)
            .select_related("column", "column__dataset_type")
            .order_by("token")
        )
        if indicator
        else []
    )
    common_input_frequency, preview_input_frequency_error = _validate_input_columns_frequency(
        [inp.column for inp in inputs]
    )
    requested_frequency = _parse_frequency(request.GET.get("frequency") or (indicator.frequency if indicator else None))
    frequency = common_input_frequency or requested_frequency
    start_date, end_date = _get_date_range(
        frequency, request.GET.get("date_start"), request.GET.get("date_end")
    )
    if inputs and not preview_input_frequency_error:
        common_available_range = _derive_common_available_period_range(
            inputs=inputs,
            frequency=frequency,
        )
        if common_available_range:
            start_date, end_date = common_available_range
    periods: list[tuple[date, date]] = []
    chart_labels: list[str] = []
    chart_title = ""
    preview_supported = False
    if indicator:
        preview_supported = bool(indicator.expression)
        if not preview_supported:
            preview_supported = indicator.variables.filter(is_active=True).exists()
    if indicator and preview_supported:
        periods, chart_labels, chart_title = _build_periods(frequency, start_date, end_date)
    chart_values: list[float | None] = []
    preview_rows: list[dict] = []
    preview_periods_requested_count = len(periods)
    preview_common_periods_count = 0
    preview_skipped_no_common_data = 0
    used_cached_preview = False
    used_fast_preview = False
    if indicator and preview_supported and not recalculate and not preview_input_frequency_error:
        existing_cached_results = list(
            PerformanceIndicatorResult.objects.filter(
                indicator=indicator,
                entity=entity,
                frequency=frequency,
                period_end__gte=start_date,
                period_end__lte=end_date,
            ).order_by("period_end")
        )
        if existing_cached_results:
            used_cached_preview = True
            chart_labels = []
            for res in existing_cached_results:
                label = _format_result_label(
                    frequency=frequency,
                    period_start=getattr(res, "period_start", None),
                    period_end=res.period_end,
                )
                chart_labels.append(label)
                chart_values.append(res.numeric_value if res.status == PerformanceIndicatorResult.STATUS_SUCCESS else None)
                preview_rows.append(
                    {
                        "label": label,
                        "status": res.status,
                        "value": (res.numeric_value if res.status == PerformanceIndicatorResult.STATUS_SUCCESS else None),
                    }
                )
            preview_common_periods_count = len(existing_cached_results)

    if (
        indicator
        and periods
        and not preview_input_frequency_error
        and not used_cached_preview
        and bool(indicator.expression)
    ):
        fast_preview = _compute_expression_preview_fast(
            indicator=indicator,
            entity=entity,
            inputs=inputs,
            periods=periods,
            labels=chart_labels,
            frequency=frequency,
        )
        chart_labels = list(fast_preview.get("chart_labels") or [])
        chart_values = list(fast_preview.get("chart_values") or [])
        preview_rows = list(fast_preview.get("preview_rows") or [])
        preview_common_periods_count = int(fast_preview.get("preview_common_periods_count") or 0)
        preview_skipped_no_common_data = int(fast_preview.get("preview_skipped_no_common_data") or 0)
        used_fast_preview = True

    if indicator and periods and not preview_input_frequency_error and not used_cached_preview and not used_fast_preview:
        periods, chart_labels, skipped_preview_periods = _filter_periods_with_complete_inputs(
            indicator=indicator,
            inputs=inputs,
            periods=periods,
            labels=chart_labels,
            frequency=frequency,
        )
        preview_common_periods_count = len(periods)
        preview_skipped_no_common_data = skipped_preview_periods
        if periods and recalculate:
            recalculate = True
    if indicator and periods and not preview_input_frequency_error and not used_cached_preview and not used_fast_preview:
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
    elif preview_input_frequency_error:
        messages.error(request, preview_input_frequency_error)
    chart_values = _sanitize_chart_values(chart_values)
    column_options = list(
        ColumnDef.objects.filter(
            dataset_type__entity=entity,
            dataset_type__status=DatasetType.STATUS_APPROVED,
            dataset_type__is_active=True,
            data_type__in=FORMULA_INPUT_COLUMN_TYPES,
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
        "formula_input_frequency": common_input_frequency,
        "formula_input_frequency_error": preview_input_frequency_error,
        "preview_periods_requested_count": preview_periods_requested_count,
        "preview_common_periods_count": preview_common_periods_count,
        "preview_skipped_no_common_data": preview_skipped_no_common_data,
        "preview_has_numeric_values": any(v is not None for v in chart_values),
    }
    return render(request, "performance/formulas.html", context)
