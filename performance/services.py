from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from calendar import monthrange

from django.db.models import Avg, Max, Min, Sum

from ingest.models import PublishedDataPoint
from performance.models import (
    FREQ_DAILY,
    FREQ_MONTHLY,
    FREQ_WEEKLY,
    FREQ_YEARLY,
    PerformanceIndicator,
    PerformanceIndicatorInput,
    PerformanceIndicatorResult,
    PerformanceVariable,
)


@dataclass(frozen=True)
class MonthWindow:
    period_start: date
    period_end: date


def month_window(year: int, month: int) -> MonthWindow:
    last_day = monthrange(year, month)[1]
    return MonthWindow(date(year, month, 1), date(year, month, last_day))


def shift_months(d: date, months: int) -> date:
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def shift_period(d: date, frequency: str, offset: int) -> date:
    if offset == 0:
        return d
    if frequency == FREQ_DAILY:
        return d - timedelta(days=offset)
    if frequency == FREQ_WEEKLY:
        return d - timedelta(weeks=offset)
    if frequency == FREQ_YEARLY:
        return shift_months(d, -(offset * 12))
    return shift_months(d, -offset)


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except Exception:
        return False


def _to_rpn(tokens: list[str]) -> list[str]:
    output: list[str] = []
    stack: list[str] = []
    precedence = {"+": 1, "-": 1, "*": 2, "/": 2}
    for tok in tokens:
        if tok in precedence:
            while stack and stack[-1] in precedence and precedence[stack[-1]] >= precedence[tok]:
                output.append(stack.pop())
            stack.append(tok)
        elif tok == "(":
            stack.append(tok)
        elif tok == ")":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
            if not stack:
                raise ValueError("paréntesis no balanceados")
            stack.pop()
        else:
            output.append(tok)
    while stack:
        if stack[-1] in ("(", ")"):
            raise ValueError("paréntesis no balanceados")
        output.append(stack.pop())
    return output


def evaluate_expression(tokens: list[str], values: dict[str, float]) -> tuple[float | None, str | None]:
    if not tokens:
        return None, "expresión vacía"
    try:
        rpn = _to_rpn(tokens)
    except ValueError as exc:
        return None, str(exc)
    stack: list[float] = []
    for tok in rpn:
        if tok in {"+", "-", "*", "/"}:
            if len(stack) < 2:
                return None, "expresión inválida"
            b = stack.pop()
            a = stack.pop()
            if tok == "+":
                stack.append(a + b)
            elif tok == "-":
                stack.append(a - b)
            elif tok == "*":
                stack.append(a * b)
            elif tok == "/":
                if b == 0:
                    return None, "división por cero"
                stack.append(a / b)
        else:
            if tok in values:
                stack.append(values[tok])
            elif _is_number(tok):
                stack.append(float(tok))
            else:
                return None, f"token desconocido: {tok}"
    if len(stack) != 1:
        return None, "expresión inválida"
    return stack[0], None


def resolve_variable_value(variable: PerformanceVariable, window: MonthWindow) -> tuple[float | None, dict]:
    """
    Resuelve el valor numérico de una variable metodológica para una ventana mensual.
    Devuelve (valor, traza).
    """

    mappings = list(
        variable.mappings.filter(is_active=True)
        .select_related("dataset_type", "column")
        .order_by("-updated_at")
    )
    trace: dict = {"variable": variable.key, "mappings": [m.id for m in mappings]}

    if not mappings:
        trace["error"] = "Se requiere al menos 1 mapping activo para esta variable"
        return None, trace

    if len(mappings) > 1:
        trace["warning"] = "Se encontraron multiples mappings activos; se usa el mas reciente"

    mapping = mappings[0]
    shifted_start = shift_months(window.period_start, -mapping.offset_months)
    shifted_end = shift_months(window.period_end, -mapping.offset_months)

    qs = (
        PublishedDataPoint.objects.filter(
            instance__entity=variable.entity,
            instance__dataset_type=mapping.dataset_type,
            instance__period__gte=shifted_start,
            instance__period__lte=shifted_end,
            column=mapping.column,
            numeric_value__isnull=False,
        )
        .values_list("numeric_value", flat=True)
    )

    agg = mapping.aggregation.upper()
    value: float | None
    if agg == "SUM":
        value = qs.aggregate(v=Sum("numeric_value"))["v"]
    elif agg == "AVG":
        value = qs.aggregate(v=Avg("numeric_value"))["v"]
    elif agg == "MAX":
        value = qs.aggregate(v=Max("numeric_value"))["v"]
    elif agg == "MIN":
        value = qs.aggregate(v=Min("numeric_value"))["v"]
    elif agg == "NONE":
        # "NONE": exige un único valor publicado en la ventana
        values = list(qs[:2])
        if len(values) == 1:
            value = float(values[0])
        else:
            value = None
            trace["error"] = f"NONE requiere 1 valor; se encontraron {len(values)}"
    elif agg == "LAST":
        # LAST: último por fecha (period) y luego por id
        last = (
            PublishedDataPoint.objects.filter(
                instance__entity=variable.entity,
                instance__dataset_type=mapping.dataset_type,
                instance__period__gte=shifted_start,
                instance__period__lte=shifted_end,
                column=mapping.column,
                numeric_value__isnull=False,
            )
            .order_by("-instance__period", "-id")
            .values_list("numeric_value", flat=True)
            .first()
        )
        value = float(last) if last is not None else None
    else:
        value = None
        trace["error"] = f"Aggregation no soportada: {agg}"

    if value is None:
        trace.update(
            {
                "dataset": mapping.dataset_type.slug,
                "column": mapping.column.name,
                "aggregation": agg,
                "window_used": [shifted_start.isoformat(), shifted_end.isoformat()],
                "transform": mapping.transform,
                "transform_value": mapping.transform_value,
                "value": None,
            }
        )
        return None, trace

    transform = mapping.transform.upper()
    if transform == "MULTIPLY":
        if mapping.transform_value is None:
            trace["error"] = "transform MULTIPLY requiere transform_value"
            return None, trace
        value = float(value) * float(mapping.transform_value)
    elif transform == "ADD":
        if mapping.transform_value is None:
            trace["error"] = "transform ADD requiere transform_value"
            return None, trace
        value = float(value) + float(mapping.transform_value)
    elif transform == "NONE":
        pass
    else:
        trace["error"] = f"Transform no soportada: {transform}"
        return None, trace

    trace.update(
        {
            "dataset": mapping.dataset_type.slug,
            "column": mapping.column.name,
            "aggregation": agg,
            "window_used": [shifted_start.isoformat(), shifted_end.isoformat()],
            "transform": transform,
            "transform_value": mapping.transform_value,
            "value": value,
        }
    )
    return float(value), trace


def resolve_input_value(
    input_def: PerformanceIndicatorInput,
    window: MonthWindow,
    *,
    frequency: str,
) -> tuple[float | None, dict]:
    column = input_def.column
    dataset_type = column.dataset_type
    shifted_start = shift_period(window.period_start, frequency, input_def.offset_periods)
    shifted_end = shift_period(window.period_end, frequency, input_def.offset_periods)

    qs = (
        PublishedDataPoint.objects.filter(
            instance__entity=input_def.indicator.entity,
            instance__dataset_type=dataset_type,
            instance__period__gte=shifted_start,
            instance__period__lte=shifted_end,
            column=column,
            numeric_value__isnull=False,
        )
        .values_list("numeric_value", flat=True)
    )

    trace: dict = {
        "token": input_def.token,
        "column": column.name,
        "dataset": dataset_type.slug,
        "aggregation": input_def.aggregation,
        "window_used": [shifted_start.isoformat(), shifted_end.isoformat()],
    }

    agg = input_def.aggregation.upper()
    value: float | None
    if agg == "SUM":
        value = qs.aggregate(v=Sum("numeric_value"))["v"]
    elif agg == "AVG":
        value = qs.aggregate(v=Avg("numeric_value"))["v"]
    elif agg == "MAX":
        value = qs.aggregate(v=Max("numeric_value"))["v"]
    elif agg == "MIN":
        value = qs.aggregate(v=Min("numeric_value"))["v"]
    elif agg == "NONE":
        values = list(qs[:2])
        if len(values) == 1:
            value = float(values[0])
        else:
            value = None
            trace["error"] = f"NONE requiere 1 valor; se encontraron {len(values)}"
    elif agg == "LAST":
        last = (
            PublishedDataPoint.objects.filter(
                instance__entity=input_def.indicator.entity,
                instance__dataset_type=dataset_type,
                instance__period__gte=shifted_start,
                instance__period__lte=shifted_end,
                column=column,
                numeric_value__isnull=False,
            )
            .order_by("-instance__period", "-id")
            .values_list("numeric_value", flat=True)
            .first()
        )
        value = float(last) if last is not None else None
    else:
        value = None
        trace["error"] = f"Aggregation no soportada: {agg}"

    if value is None:
        return None, trace

    transform = input_def.transform.upper()
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
    elif transform == "NONE":
        pass
    else:
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


def _compute_indicator_value(
    key: str,
    variable_values: dict[str, float],
    variable_traces: dict[str, dict],
) -> tuple[float | None, str, dict]:
    try:
        if key == "pcs.formula1_yield_pct":
            msales = variable_values["pcs.f1.msales_tm"]
            msalmuera = variable_values["pcs.f1.msalmuera_tm"]
            xsolids = variable_values["pcs.f1.xsolids_frac"]
            denom = msalmuera * xsolids
            if denom <= 0:
                return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {
                    "variables": variable_traces,
                    "error": "denominator<=0",
                }
            return (msales / denom) * 100.0, PerformanceIndicatorResult.STATUS_SUCCESS, {"variables": variable_traces}

        if key == "pcs.energy_specific_boe_per_tm":
            e = variable_values["pcs.energy_equivalent_boe"]
            prod = variable_values["pcs.salts_mass_tm"]
            if prod <= 0:
                return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {
                    "variables": variable_traces,
                    "error": "denominator<=0",
                }
            return e / prod, PerformanceIndicatorResult.STATUS_SUCCESS, {"variables": variable_traces}

        if key == "kcl.yield_pct":
            p = variable_values["kcl.product_mass_tm"]
            feed = variable_values["kcl.feed_mass_tm"]
            if feed <= 0:
                return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {
                    "variables": variable_traces,
                    "error": "denominator<=0",
                }
            return (p / feed) * 100.0, PerformanceIndicatorResult.STATUS_SUCCESS, {"variables": variable_traces}

        if key == "lic.yield_pct":
            p = variable_values["lic.product_mass_tm"]
            feed = variable_values["lic.feed_mass_tm"]
            if feed <= 0:
                return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {
                    "variables": variable_traces,
                    "error": "denominator<=0",
                }
            return (p / feed) * 100.0, PerformanceIndicatorResult.STATUS_SUCCESS, {"variables": variable_traces}

        return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {
            "variables": variable_traces,
            "error": "indicador no implementado",
        }
    except Exception as exc:
        return None, PerformanceIndicatorResult.STATUS_ERROR, {
            "variables": variable_traces,
            "exception": str(exc),
        }


def _compute_indicator_expression(
    indicator: PerformanceIndicator,
    window: MonthWindow,
    *,
    frequency: str,
) -> tuple[float | None, str, dict]:
    inputs = list(
        indicator.inputs.filter(is_active=True)
        .select_related("column", "column__dataset_type")
        .order_by("token")
    )
    if not inputs:
        return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {
            "error": "sin variables configuradas",
        }

    values: dict[str, float] = {}
    traces: dict[str, dict] = {}
    for inp in inputs:
        val, tr = resolve_input_value(inp, window, frequency=frequency)
        traces[inp.token] = tr
        if val is None:
            return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {"inputs": traces}
        values[inp.token] = float(val)

    tokens_raw = indicator.expression or []
    tokens = [str(t) for t in tokens_raw] if isinstance(tokens_raw, list) else []
    value, err = evaluate_expression(tokens, values)
    if err:
        status = (
            PerformanceIndicatorResult.STATUS_NOT_CALCULABLE
            if err == "división por cero"
            else PerformanceIndicatorResult.STATUS_ERROR
        )
        return None, status, {"inputs": traces, "error": err, "expression": tokens}
    return float(value), PerformanceIndicatorResult.STATUS_SUCCESS, {"inputs": traces, "expression": tokens}


def compute_indicator(
    indicator: PerformanceIndicator,
    window: MonthWindow,
    *,
    frequency: str,
) -> tuple[float | None, str, dict]:
    """
    Devuelve (valor, status, trace).

    Implementacion inicial para 3 indicadores semilla; el resto queda NO_CALCULABLE.
    """

    if indicator.expression:
        return _compute_indicator_expression(indicator, window, frequency=frequency)

    if frequency not in {FREQ_DAILY, FREQ_MONTHLY}:
        return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {
            "error": "frecuencia no soportada para fórmulas legacy",
        }

    variable_values: dict[str, float] = {}
    variable_traces: dict[str, dict] = {}
    for v in indicator.variables.filter(is_active=True):
        val, tr = resolve_variable_value(v, window)
        variable_traces[v.key] = tr
        if val is None:
            return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {"variables": variable_traces}
        variable_values[v.key] = float(val)

    return _compute_indicator_value(indicator.key, variable_values, variable_traces)


def compute_indicator_for_stage(
    indicator: PerformanceIndicator,
    window: MonthWindow,
    *,
    stage: str,
    frequency: str,
) -> tuple[float | None, str, dict]:
    """
    Compatibilidad: usa los mapeos activos sin diferenciar stage.
    """
    if indicator.expression:
        return _compute_indicator_expression(indicator, window, frequency=frequency)

    variable_values: dict[str, float] = {}
    variable_traces: dict[str, dict] = {}
    for v in indicator.variables.filter(is_active=True):
        val, tr = resolve_variable_value(v, window)
        variable_traces[v.key] = tr
        if val is None:
            return None, PerformanceIndicatorResult.STATUS_NOT_CALCULABLE, {"variables": variable_traces}
        variable_values[v.key] = float(val)

    return _compute_indicator_value(indicator.key, variable_values, variable_traces)


def compute_and_store_indicators(
    entity,
    window: MonthWindow,
    *,
    frequency: str,
) -> int:
    indicators = list(
        PerformanceIndicator.objects.filter(entity=entity, is_active=True)
        .prefetch_related("variables")
        .order_by("key")
    )
    updated = 0
    for indicator in indicators:
        value, status, trace = compute_indicator(indicator, window, frequency=frequency)
        PerformanceIndicatorResult.objects.update_or_create(
            indicator=indicator,
            entity=entity,
            period_end=window.period_end,
            frequency=frequency,
            defaults={
                "period_start": window.period_start,
                "stage": "DRAFT",
                "status": status,
                "numeric_value": value,
                "text_value": "",
                "trace": trace,
            },
        )
        updated += 1
    return updated


def resolve_variable_value_for_stage(
    variable: PerformanceVariable, window: MonthWindow, *, stage: str
) -> tuple[float | None, dict]:
    mappings = list(
        variable.mappings.filter(is_active=True, stage=stage)
        .select_related("dataset_type", "column")
    )
    trace: dict = {"variable": variable.key, "stage": stage, "mappings": [m.id for m in mappings]}

    if len(mappings) != 1:
        trace["error"] = "Se requiere exactamente 1 mapping activo para esta variable y stage"
        return None, trace

    mapping = mappings[0]
    # Reusar lógica de resolve_variable_value, pero con este mapping fijo:
    shifted_start = shift_months(window.period_start, -mapping.offset_months)
    shifted_end = shift_months(window.period_end, -mapping.offset_months)

    qs = (
        PublishedDataPoint.objects.filter(
            instance__entity=variable.entity,
            instance__dataset_type=mapping.dataset_type,
            instance__period__gte=shifted_start,
            instance__period__lte=shifted_end,
            column=mapping.column,
            numeric_value__isnull=False,
        )
        .values_list("numeric_value", flat=True)
    )

    agg = mapping.aggregation.upper()
    value: float | None
    if agg == "SUM":
        value = qs.aggregate(v=Sum("numeric_value"))["v"]
    elif agg == "AVG":
        value = qs.aggregate(v=Avg("numeric_value"))["v"]
    elif agg == "MAX":
        value = qs.aggregate(v=Max("numeric_value"))["v"]
    elif agg == "MIN":
        value = qs.aggregate(v=Min("numeric_value"))["v"]
    elif agg == "NONE":
        values = list(qs[:2])
        if len(values) == 1:
            value = float(values[0])
        else:
            value = None
            trace["error"] = f"NONE requiere 1 valor; se encontraron {len(values)}"
    elif agg == "LAST":
        last = (
            PublishedDataPoint.objects.filter(
                instance__entity=variable.entity,
                instance__dataset_type=mapping.dataset_type,
                instance__period__gte=shifted_start,
                instance__period__lte=shifted_end,
                column=mapping.column,
                numeric_value__isnull=False,
            )
            .order_by("-instance__period", "-id")
            .values_list("numeric_value", flat=True)
            .first()
        )
        value = float(last) if last is not None else None
    else:
        value = None
        trace["error"] = f"Aggregation no soportada: {agg}"

    if value is None:
        trace.update(
            {
                "dataset": mapping.dataset_type.slug,
                "column": mapping.column.name,
                "aggregation": agg,
                "window_used": [shifted_start.isoformat(), shifted_end.isoformat()],
            }
        )
        return None, trace

    transform = mapping.transform.upper()
    if transform == "MULTIPLY":
        if mapping.transform_value is None:
            trace["error"] = "transform MULTIPLY requiere transform_value"
            return None, trace
        value = float(value) * float(mapping.transform_value)
    elif transform == "ADD":
        if mapping.transform_value is None:
            trace["error"] = "transform ADD requiere transform_value"
            return None, trace
        value = float(value) + float(mapping.transform_value)
    elif transform == "NONE":
        pass
    else:
        trace["error"] = f"Transform no soportada: {transform}"
        return None, trace

    trace.update(
        {
            "dataset": mapping.dataset_type.slug,
            "column": mapping.column.name,
            "aggregation": agg,
            "window_used": [shifted_start.isoformat(), shifted_end.isoformat()],
            "transform": transform,
            "transform_value": mapping.transform_value,
            "offset_months": mapping.offset_months,
            "value": float(value),
        }
    )
    return float(value), trace
