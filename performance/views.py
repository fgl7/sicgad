from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import json

from accounts.decorators import admin_required
from performance.forms import ColumnOption, VariableMappingForm
from performance.models import PerformanceIndicator, PerformanceIndicatorResult, PerformanceVariable, PerformanceVariableMapping
from performance.services import compute_indicator_for_stage, month_window, shift_months
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


@admin_required
def pcs_formula_1(request: HttpRequest) -> HttpResponse:
    """
    MVP UI: Formula 1 (PCS) - Rendimiento de Producción Mensual (%)

    Permite al Admin asignar variables Msales(m), Msalmuera(m-delta_t), Xsolids(m-delta_t)
    a columnas de esquemas (por planta) y ver resultado Draft/Certificado.
    """

    plant = Plant.objects.filter(code="PCS").first()
    if not plant:
        messages.error(request, "No existe la planta PCS en el sistema.")
        return redirect("home")

    indicator = PerformanceIndicator.objects.filter(key="pcs.formula1_yield_pct", plant=plant).first()
    if not indicator:
        messages.error(request, "No existe el indicador pcs.formula1_yield_pct. Ejecute seed_performance_catalog.")
        return redirect("home")

    # Mes seleccionado
    month_param = request.GET.get("month") if request.method == "GET" else request.POST.get("month")
    parsed = _parse_month(month_param)
    today = timezone.now().date()
    year, month = parsed if parsed else (today.year, today.month)
    window = month_window(year, month)

    # Column options por planta: solo esquemas aprobados y activos
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

    # Variables de la fórmula 1
    variables = list(
        PerformanceVariable.objects.filter(
            plant=plant,
            key__in=["pcs.f1.msales_tm", "pcs.f1.msalmuera_tm", "pcs.f1.xsolids_frac"],
            is_active=True,
        ).order_by("key")
    )
    variables_by_key = {v.key: v for v in variables}

    # Preload mappings
    mappings = list(
        PerformanceVariableMapping.objects.filter(variable__in=variables, is_active=True)
        .select_related("dataset_type", "column")
        .order_by("variable__key", "stage", "-updated_at")
    )
    mapping_by_var_stage: dict[tuple[str, str], PerformanceVariableMapping] = {}
    for m in mappings:
        k = (m.variable.key, m.stage)
        if k not in mapping_by_var_stage:
            mapping_by_var_stage[k] = m

    # Forms per variable-stage
    forms: dict[tuple[str, str], VariableMappingForm] = {}
    stages = ["DRAFT", "CERTIFIED"]
    for v in variables:
        for stage in stages:
            existing = mapping_by_var_stage.get((v.key, stage))
            initial = {
                "column_id": str(existing.column_id) if existing else "",
                "aggregation": existing.aggregation if existing else "SUM",
                "offset_months": existing.offset_months if existing else 0,
            }
            safe_prefix = v.key.replace(".", "_").replace("-", "_")
            prefix = f"{safe_prefix}__{stage}"
            if request.method == "POST":
                forms[(v.key, stage)] = VariableMappingForm(
                    request.POST,
                    prefix=prefix,
                    column_options=column_options,
                )
            else:
                forms[(v.key, stage)] = VariableMappingForm(
                    initial=initial,
                    prefix=prefix,
                    column_options=column_options,
                )

    if request.method == "POST":
        all_valid = all(f.is_valid() for f in forms.values())
        if not all_valid:
            messages.error(request, "Hay errores en el formulario. Revise las asignaciones.")
        else:
            with transaction.atomic():
                for (var_key, stage), form in forms.items():
                    variable = variables_by_key[var_key]
                    column = form.resolve_column()
                    aggregation = form.cleaned_data["aggregation"]
                    offset_months = form.cleaned_data["offset_months"]

                    # Si no selecciona columna, desactiva mappings existentes para ese var+stage.
                    if column is None:
                        PerformanceVariableMapping.objects.filter(
                            variable=variable,
                            stage=stage,
                            is_active=True,
                        ).update(is_active=False)
                        continue

                    dataset = column.dataset_type
                    if dataset.plant_id != plant.id:
                        raise ValueError("Asignación inválida: la columna no pertenece a la planta PCS.")

                    # Mantener un solo mapping activo por var+stage (MVP)
                    PerformanceVariableMapping.objects.filter(
                        variable=variable,
                        stage=stage,
                        is_active=True,
                    ).update(is_active=False)

                    PerformanceVariableMapping.objects.create(
                        variable=variable,
                        dataset_type=dataset,
                        column=column,
                        aggregation=aggregation,
                        transform="NONE",
                        transform_value=None,
                        offset_months=offset_months,
                        stage=stage,
                        notes="Asignado desde UI (Fórmula 1 PCS)",
                        is_active=True,
                    )

            messages.success(request, "Asignaciones guardadas.")
            return redirect(f"/performance/pcs/formula-1/?month={year:04d}-{month:02d}")

    # Cálculo/preview (no persiste, solo muestra)
    preview: dict[str, dict] = {}
    for stage in stages:
        value, status, trace = compute_indicator_for_stage(indicator, window, stage=stage)
        preview[stage] = {"value": value, "status": status, "trace": trace}

    # Serie histórica (últimos 12 meses) calculada al vuelo
    base_month = date(year, month, 1)
    month_starts = [shift_months(base_month, -i) for i in range(11, -1, -1)]
    chart_labels = [m.strftime("%Y-%m") for m in month_starts]
    chart_draft: list[float | None] = []
    chart_cert: list[float | None] = []
    for m in month_starts:
        w = month_window(m.year, m.month)
        v_d, s_d, _ = compute_indicator_for_stage(indicator, w, stage="DRAFT")
        v_c, s_c, _ = compute_indicator_for_stage(indicator, w, stage="CERTIFIED")
        chart_draft.append(v_d if s_d == PerformanceIndicatorResult.STATUS_SUCCESS else None)
        chart_cert.append(v_c if s_c == PerformanceIndicatorResult.STATUS_SUCCESS else None)

    context = {
        "plant": plant,
        "month": f"{year:04d}-{month:02d}",
        "indicator": indicator,
        "variable_blocks": [
            {
                "variable": v,
                "draft_form": forms[(v.key, "DRAFT")],
                "cert_form": forms[(v.key, "CERTIFIED")],
            }
            for v in variables
        ],
        "preview": preview,
        "chart_labels_json": json.dumps(chart_labels),
        "chart_draft_json": json.dumps(chart_draft),
        "chart_cert_json": json.dumps(chart_cert),
    }
    return render(request, "performance/pcs_formula_1.html", context)
