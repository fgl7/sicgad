from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Membership
from accounts.decorators import admin_role_required
from audit.utils import record_action
from ingest.models import DatasetInstance, PublishedDataPoint
from ingest.utils import _read_instance_file, parse_date_cell
from schemas.models import ColumnDef, DatasetType
from .forms import ProjectForm, ProjectReportConfigForm
from .models import Project
from .models import ProjectReportConfig


PUBLISHED_STATES = {
    DatasetInstance.STATE_PUBLISHED,
    DatasetInstance.STATE_LOCKED,
}

MONTH_LABELS = [
    "ENE",
    "FEB",
    "MAR",
    "ABR",
    "MAY",
    "JUN",
    "JUL",
    "AGO",
    "SEP",
    "OCT",
    "NOV",
    "DIC",
]

MONTH_ALIASES = {
    "ene": 1,
    "enero": 1,
    "feb": 2,
    "febrero": 2,
    "mar": 3,
    "marzo": 3,
    "abr": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "jun": 6,
    "junio": 6,
    "jul": 7,
    "julio": 7,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "sept": 9,
    "septiembre": 9,
    "setiembre": 9,
    "oct": 10,
    "octubre": 10,
    "nov": 11,
    "noviembre": 11,
    "dic": 12,
    "diciembre": 12,
}

SUMMARY_ALIASES = {
    "location": ("ubicacion", "ubicacion_proyecto", "location"),
    "executor": ("ejecutor", "executor"),
    "description": ("descripcion", "descripcion_proyecto", "description"),
    "budget_mmbs": ("presupuesto_mmbs", "presupuesto_inversion_mmbs", "budget_mmbs"),
    "start_date": ("fecha_inicio", "start_date"),
    "end_date": ("fecha_conclusion", "fecha_fin", "end_date"),
    "stage": ("etapa_actual", "stage", "etapa"),
    "execution_physical_pct": (
        "ejecucion_fisica_pct",
        "fisica_pct",
        "ejecucion_fisica",
        "ejecucion_fisica_acumulada",
    ),
    "execution_financial_mmbs": (
        "ejecucion_financiera_mmbs",
        "financiera_mmbs",
        "ejecucion_financiera_acumulada",
    ),
    "execution_programmed_mmbs": (
        "programado_mmbs",
        "programado_2025_mmbs",
        "ejecucion_programada_anual",
    ),
    "execution_executed_mmbs": (
        "ejecutado_mmbs",
        "ejecutado_2025_mmbs",
        "ejecucion_anual",
    ),
    "status": ("estado_situacion", "situacion", "estado_de_situacion"),
    "justification": (
        "justificacion_desviacion",
        "justificacion",
        "justificacion_desviacion_curva_s",
    ),
    "actions": ("acciones_preventivas", "acciones"),
    "report_date": ("fecha_corte", "fecha_reporte"),
}

PROGRAM_VALUE_KEYS = ("programado_pct", "programado", "porcentaje", "pct", "valor")
EXECUTED_VALUE_KEYS = ("ejecutado_pct", "ejecutado", "porcentaje", "pct", "valor")
MONTH_KEYS = ("mes", "month", "periodo", "period")


def _get_role_flags(user):
    if not user.is_authenticated:
        return False, False, False
    is_admin = user.is_superuser or Membership.objects.filter(
        user=user, role="ADMIN", is_active=True
    ).exists()
    is_loader = Membership.objects.filter(user=user, role="LOADER", is_active=True).exists()
    is_validator = Membership.objects.filter(
        user=user, role="VALIDATOR", is_active=True
    ).exists()
    return is_admin, is_loader, is_validator


def _can_access_project(user, project) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser or Membership.objects.filter(
        user=user, role="ADMIN", is_active=True
    ).exists():
        return True
    memberships = Membership.objects.filter(user=user, is_active=True)
    if memberships.filter(entity__isnull=True).exists():
        return True
    allowed_entities = set(memberships.exclude(entity__isnull=True).values_list("entity_id", flat=True))
    project_entities = set(project.entities.values_list("id", flat=True))
    return bool(allowed_entities.intersection(project_entities))


def _to_float(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_month(value) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.month
    if isinstance(value, date):
        return value.month

    parsed = parse_date_cell(value)
    if parsed:
        return parsed.month

    text = str(value).strip().lower()
    if not text:
        return None

    if text.isdigit():
        month = int(text)
        return month if 1 <= month <= 12 else None

    for fmt in ("%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt).month
        except ValueError:
            continue

    key = text[:3]
    return MONTH_ALIASES.get(text) or MONTH_ALIASES.get(key)


def _month_number_from_label(label: str | None) -> int | None:
    if not label:
        return None
    text = str(label).strip().lower()
    if not text:
        return None
    if text in MONTH_ALIASES:
        return MONTH_ALIASES[text]
    key = text[:3]
    return MONTH_ALIASES.get(key)


def _extract_month_values_from_rows(rows):
    month_values: dict[int, float] = {}
    for row in rows:
        for key, value in row.items():
            month = _month_number_from_label(key)
            if not month:
                continue
            parsed = _to_float(value)
            if parsed is None:
                continue
            month_values[month] = parsed
    return month_values


def _extract_row_value(row, columns, candidate_keys):
    for key in candidate_keys:
        if key in row:
            value = _to_float(row.get(key))
            if value is not None:
                return value
    for column in columns:
        if column.data_type in ("INTEGER", "FLOAT") and column.name in row:
            value = _to_float(row.get(column.name))
            if value is not None:
                return value
    return None


def _load_instance_rows(instance: DatasetInstance | None, columns: list[ColumnDef]):
    if not instance:
        return []

    if instance.state in PUBLISHED_STATES:
        points = (
            PublishedDataPoint.objects.filter(instance=instance, column__in=columns)
            .select_related("column")
            .order_by("row_index", "column__display_order", "column__name")
        )
        rows = {}
        for point in points:
            row = rows.setdefault(point.row_index, {})
            if point.numeric_value is not None:
                value = point.numeric_value
            elif point.date_value is not None:
                value = point.date_value
            elif point.bool_value is not None:
                value = bool(point.bool_value)
            else:
                value = point.text_value
            row[point.column.name] = value
        return [rows[idx] for idx in sorted(rows.keys())]

    header, parsed_rows = _read_instance_file(instance)
    if not header:
        return []

    header_map = {}
    for col in columns:
        if col.name:
            header_map[col.name.strip().lower()] = col.name
        if col.label:
            header_map[col.label.strip().lower()] = col.name

    index_map = [header_map.get((name or "").strip().lower()) for name in header]
    rows = []
    for parsed in parsed_rows:
        row = {}
        for idx, raw in enumerate(parsed.values):
            col_name = index_map[idx] if idx < len(index_map) else None
            if not col_name:
                continue
            row[col_name] = raw
        if row:
            rows.append(row)
    return rows


def _resolve_summary_value(row, keys, fallback):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return fallback


def _pick_year(request, fallback_year: int | None = None) -> int:
    year_param = (request.GET.get("year") or "").strip()
    if year_param.isdigit():
        year = int(year_param)
        if 2000 <= year <= 2100:
            return year
    if fallback_year:
        return fallback_year
    return timezone.now().year


@admin_role_required
def project_list(request):
    projects = Project.objects.prefetch_related("entities").order_by("name")
    return render(request, "projects/project_list.html", {"projects": projects})


@admin_role_required
def project_create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            record_action(
                "OTHER",
                request=request,
                module="Projects",
                object_repr=f"Proyecto {project.name} creado",
                details="Creado desde panel de proyectos.",
            )
            return redirect("projects:project_list")
    else:
        form = ProjectForm()
    return render(
        request,
        "projects/project_form.html",
        {"form": form, "project": None},
    )


@admin_role_required
def project_edit(request, pk: int):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            changed = [
                field
                for field in form.changed_data
                if field in ProjectForm.STATIC_FIELDS
            ]
            if changed:
                justification = (form.cleaned_data.get("change_justification") or "").strip()
                record_action(
                    "OTHER",
                    request=request,
                    module="Projects",
                    object_repr=f"Proyecto {project.name} actualizado",
                    details=f"Campos: {', '.join(changed)}. Justificacion: {justification}",
                )
            return redirect("projects:project_list")
    else:
        form = ProjectForm(instance=project)
    return render(
        request,
        "projects/project_form.html",
        {"form": form, "project": project},
    )


@admin_role_required
def project_delete(request, pk: int):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        project.delete()
        return redirect("projects:project_list")
    return render(
        request,
        "projects/project_confirm_delete.html",
        {"project": project},
    )


@admin_role_required
def report_config_list(request):
    configs = ProjectReportConfig.objects.select_related(
        "project",
        "report_dataset",
        "curve_program_dataset",
        "curve_executed_dataset",
    ).order_by("project__name", "name")
    return render(
        request,
        "projects/report_config_list.html",
        {"configs": configs},
    )


@admin_role_required
def report_config_create(request):
    if request.method == "POST":
        form = ProjectReportConfigForm(request.POST)
        if form.is_valid():
            config = form.save()
            record_action(
                "OTHER",
                request=request,
                module="Projects",
                object_repr=f"Reporte {config.name} ({config.project.name}) creado",
                details="Configuracion de reporte creada.",
            )
            return redirect("projects:report_config_list")
    else:
        form = ProjectReportConfigForm()

    return render(
        request,
        "projects/report_config_form.html",
        {"form": form, "config": None},
    )


@admin_role_required
def report_config_edit(request, config_id: int):
    config = get_object_or_404(ProjectReportConfig, pk=config_id)
    if request.method == "POST":
        form = ProjectReportConfigForm(request.POST, instance=config)
        if form.is_valid():
            config = form.save()
            record_action(
                "OTHER",
                request=request,
                module="Projects",
                object_repr=f"Reporte {config.name} ({config.project.name}) editado",
                details="Configuracion de reporte actualizada.",
            )
            return redirect("projects:report_config_list")
    else:
        form = ProjectReportConfigForm(instance=config)

    return render(
        request,
        "projects/report_config_form.html",
        {"form": form, "config": config},
    )


@admin_role_required
def report_config_delete(request, config_id: int):
    config = get_object_or_404(ProjectReportConfig, pk=config_id)
    if request.method == "POST":
        name = config.name
        project_name = config.project.name
        config.delete()
        record_action(
            "OTHER",
            request=request,
            module="Projects",
            object_repr=f"Reporte {name} ({project_name}) eliminado",
            details="Configuracion de reporte eliminada.",
        )
        return redirect("projects:report_config_list")
    return render(
        request,
        "projects/report_config_confirm_delete.html",
        {"config": config},
    )


@login_required
def report_list(request):
    user = request.user
    configs = ProjectReportConfig.objects.select_related(
        "project",
        "report_dataset",
        "curve_executed_dataset",
    ).prefetch_related("project__entities").filter(is_active=True)

    is_admin = user.is_superuser or Membership.objects.filter(
        user=user, role="ADMIN", is_active=True
    ).exists()
    if not is_admin:
        memberships = Membership.objects.filter(user=user, is_active=True)
        has_global = memberships.filter(entity__isnull=True).exists()
        if not has_global:
            entity_ids = list(
                memberships.exclude(entity__isnull=True).values_list("entity_id", flat=True)
            )
            if entity_ids:
                configs = configs.filter(project__entities__id__in=entity_ids).distinct()
            else:
                configs = configs.none()

    return render(
        request,
        "projects/report_list.html",
        {
            "configs": configs,
            "is_admin": is_admin,
        },
    )


@login_required
def report_detail(request, config_id: int):
    config = get_object_or_404(
        ProjectReportConfig.objects.select_related(
            "project",
            "report_dataset",
            "curve_program_dataset",
            "curve_executed_dataset",
        ).prefetch_related("project__entities"),
        pk=config_id,
        is_active=True,
    )

    if not _can_access_project(request.user, config.project):
        return render(request, "projects/report_denied.html", {"config": config})

    is_admin, is_loader, is_validator = _get_role_flags(request.user)
    can_see_drafts = is_admin or is_loader or is_validator

    source = (request.GET.get("source") or "published").lower()
    if source not in ("published", "draft"):
        source = "published"
    if source == "draft" and not can_see_drafts:
        source = "published"

    summary_columns = list(
        config.report_dataset.columns.filter(is_active=True).order_by("display_order", "name")
    )
    program_columns = list(
        config.curve_program_dataset.columns.filter(is_active=True).order_by(
            "display_order", "name"
        )
    )
    executed_columns = list(
        config.curve_executed_dataset.columns.filter(is_active=True).order_by(
            "display_order", "name"
        )
    )

    summary_qs = DatasetInstance.objects.filter(dataset_type=config.report_dataset)
    program_qs = DatasetInstance.objects.filter(dataset_type=config.curve_program_dataset)
    executed_qs = DatasetInstance.objects.filter(dataset_type=config.curve_executed_dataset)

    if source == "published":
        summary_qs = summary_qs.filter(state__in=PUBLISHED_STATES)
        program_qs = program_qs.filter(state__in=PUBLISHED_STATES)
        executed_qs = executed_qs.filter(state__in=PUBLISHED_STATES)
    else:
        summary_qs = summary_qs.exclude(state__in=PUBLISHED_STATES)
        program_qs = program_qs.exclude(state__in=PUBLISHED_STATES)
        executed_qs = executed_qs.exclude(state__in=PUBLISHED_STATES)

    latest_summary = summary_qs.order_by("-period", "-created_at").first()
    fallback_year = latest_summary.period.year if latest_summary else None
    year = _pick_year(request, fallback_year)

    summary_qs = summary_qs.filter(period__year=year)
    program_qs = program_qs.filter(period__year=year)
    executed_qs = executed_qs.filter(period__year=year)

    summary_instances = list(summary_qs.order_by("period", "created_at"))
    program_instances = list(program_qs.order_by("period", "created_at"))
    executed_instances = list(executed_qs.order_by("period", "created_at"))

    executed_week_options = []
    selected_week_id = None
    executed_frequency = config.curve_executed_dataset.validation_frequency
    selected_executed_instance = None
    if executed_frequency == DatasetType.WEEKLY and executed_instances:
        for inst in executed_instances:
            iso_week = inst.period.isocalendar().week
            label = f"Semana {iso_week:02d} - {inst.period:%d/%m/%Y}"
            executed_week_options.append({"id": inst.id, "label": label})

        week_param = (request.GET.get("week") or "").strip()
        if week_param.isdigit():
            selected_week_id = int(week_param)
            selected_executed_instance = next(
                (inst for inst in executed_instances if inst.id == selected_week_id),
                None,
            )

        if selected_executed_instance is None:
            selected_executed_instance = executed_instances[-1]
            selected_week_id = selected_executed_instance.id

    selected_week_number = None
    if selected_executed_instance and selected_executed_instance.period:
        selected_week_number = selected_executed_instance.period.isocalendar().week

    summary_frequency = config.report_dataset.validation_frequency
    summary_instance = summary_instances[-1] if summary_instances else None
    if summary_frequency == DatasetType.WEEKLY and summary_instances and selected_week_number:
        matching_summary = [
            inst
            for inst in summary_instances
            if inst.period and inst.period.isocalendar().week == selected_week_number
        ]
        if matching_summary:
            summary_instance = matching_summary[-1]

    program_frequency = config.curve_program_dataset.validation_frequency
    program_instance = program_instances[-1] if program_instances else None
    if program_frequency == DatasetType.WEEKLY and program_instances:
        if selected_week_number:
            matching_program = [
                inst
                for inst in program_instances
                if inst.period and inst.period.isocalendar().week == selected_week_number
            ]
            if matching_program:
                program_instance = matching_program[-1]

    summary_rows = _load_instance_rows(summary_instance, summary_columns)
    summary_row = summary_rows[0] if summary_rows else {}

    summary = {
        "location": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["location"], config.project.location
        ),
        "executor": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["executor"], config.project.executor
        ),
        "description": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["description"], config.project.description
        ),
        "budget_mmbs": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["budget_mmbs"], config.project.budget_mmbs
        ),
        "start_date": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["start_date"], config.project.start_date
        ),
        "end_date": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["end_date"], config.project.end_date
        ),
        "stage": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["stage"], None
        ),
        "execution_physical_pct": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["execution_physical_pct"], None
        ),
        "execution_financial_mmbs": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["execution_financial_mmbs"], None
        ),
        "execution_programmed_mmbs": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["execution_programmed_mmbs"], None
        ),
        "execution_executed_mmbs": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["execution_executed_mmbs"], None
        ),
        "status": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["status"], None
        ),
        "justification": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["justification"], None
        ),
        "actions": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["actions"], None
        ),
        "report_date": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["report_date"], summary_instance.period if summary_instance else None
        ),
    }

    # Program curve (static load)
    program_values = [None] * 12
    program_rows = _load_instance_rows(program_instance, program_columns)
    program_month_map = _extract_month_values_from_rows(program_rows)
    if program_month_map:
        for month, value in program_month_map.items():
            program_values[month - 1] = value
    else:
        for row in program_rows:
            month_value = None
            for key in MONTH_KEYS:
                if key in row:
                    month_value = _parse_month(row.get(key))
                    if month_value:
                        break
            if not month_value:
                continue
            value = _extract_row_value(row, program_columns, PROGRAM_VALUE_KEYS)
            if value is not None:
                program_values[month_value - 1] = value

    # Executed curve (weekly: por semana seleccionada; otros: promedio mensual o wide)
    executed_values = [None] * 12
    if executed_frequency == DatasetType.WEEKLY and selected_executed_instance:
        rows = _load_instance_rows(selected_executed_instance, executed_columns)
        executed_month_map = _extract_month_values_from_rows(rows)
        if executed_month_map:
            for month, value in executed_month_map.items():
                executed_values[month - 1] = value
        else:
            for row in rows:
                month_value = None
                for key in MONTH_KEYS:
                    if key in row:
                        month_value = _parse_month(row.get(key))
                        if month_value:
                            break
                if not month_value:
                    continue
                value = _extract_row_value(row, executed_columns, EXECUTED_VALUE_KEYS)
                if value is not None:
                    executed_values[month_value - 1] = value
    elif executed_instances:
        latest_executed = executed_instances[-1]
        wide_rows = _load_instance_rows(latest_executed, executed_columns)
        executed_month_map = _extract_month_values_from_rows(wide_rows)
        if executed_month_map:
            for month, value in executed_month_map.items():
                executed_values[month - 1] = value
        else:
            executed_month_values: dict[int, list[float]] = defaultdict(list)
            for instance in executed_instances:
                rows = _load_instance_rows(instance, executed_columns)
                values = []
                for row in rows:
                    value = _extract_row_value(row, executed_columns, EXECUTED_VALUE_KEYS)
                    if value is not None:
                        values.append(value)
                if not values:
                    continue
                avg_value = sum(values) / len(values)
                executed_month_values[instance.period.month].append(avg_value)

            for month in range(1, 13):
                if executed_month_values.get(month):
                    values = executed_month_values[month]
                    executed_values[month - 1] = sum(values) / len(values)

    context = {
        "config": config,
        "project": config.project,
        "summary": summary,
        "summary_instance": summary_instance,
        "year": year,
        "month_labels": MONTH_LABELS,
        "program_values": program_values,
        "executed_values": executed_values,
        "chart_labels_json": json.dumps(MONTH_LABELS),
        "program_values_json": json.dumps(program_values),
        "executed_values_json": json.dumps(executed_values),
        "source": source,
        "can_see_drafts": can_see_drafts,
        "executed_week_options": executed_week_options,
        "selected_week_id": selected_week_id,
    }

    return render(request, "projects/report_detail.html", context)
