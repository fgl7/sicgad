from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import json
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.urls import reverse
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
    "company": ("empresa", "company", "contraparte", "socio"),
    "executor": ("ejecutor", "executor"),
    "description": ("descripcion", "descripcion_proyecto", "description"),
    "agreement_object": (
        "objeto_convenio",
        "objeto_del_convenio",
        "objeto",
        "agreement_object",
    ),
    "budget_mmbs": ("presupuesto_mmbs", "presupuesto_inversion_mmbs", "budget_mmbs"),
    "subscription_date": (
        "suscripcion_convenio",
        "fecha_suscripcion",
        "subscription_date",
    ),
    "addenda": ("adendas", "adenda", "addenda"),
    "execution_term": (
        "plazo_ejecucion",
        "plazo_de_ejecucion",
        "execution_term",
        "plazo",
    ),
    "start_date": ("fecha_inicio", "start_date"),
    "end_date": ("fecha_conclusion", "fecha_fin", "end_date"),
    "stage": ("etapa_actual", "stage", "etapa"),
    "planned_pct": (
        "porcentaje_planificado",
        "planificado_pct",
        "planned_pct",
    ),
    "executed_pct": (
        "porcentaje_ejecutado",
        "ejecutado_pct",
        "executed_pct",
    ),
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
CATEGORY_LABEL_KEYS = (
    "hito",
    "actividad",
    "etapa",
    "fase",
    "indicador",
    "concepto",
    "descripcion",
    "detalle",
    "item",
    "categoria",
    "milestone",
    "label",
    "nombre",
)


def _get_memberships(user):
    if not user.is_authenticated:
        return Membership.objects.none()
    return Membership.objects.filter(user=user, is_active=True)


def _is_admin_user(user) -> bool:
    if not user.is_authenticated:
        return False
    memberships = _get_memberships(user)
    return user.is_superuser or memberships.filter(role="ADMIN").exists()


def _get_loader_entity_ids(user):
    if not user.is_authenticated:
        return set()
    memberships = _get_memberships(user)
    return set(
        memberships.filter(role="LOADER", entity__isnull=False).values_list("entity_id", flat=True)
    )


def _can_user_create_projects(user) -> bool:
    return bool(_get_loader_entity_ids(user)) and not _is_admin_user(user)


def _can_user_manage_projects(user) -> bool:
    return _is_admin_user(user) or bool(_get_loader_entity_ids(user))


def _can_user_edit_project(user, project) -> bool:
    if not user.is_authenticated or _is_admin_user(user):
        return False
    if project.workflow_status == Project.STATUS_APPROVED:
        return False
    loader_entity_ids = _get_loader_entity_ids(user)
    project_entity_ids = set(project.entities.values_list("id", flat=True))
    if not loader_entity_ids.intersection(project_entity_ids):
        return False
    return project.created_by_id == user.id


def _build_schema_seed_url(project) -> str:
    base_url = reverse("schemas:schema_create")
    params = {
        "seed_source": "project",
        "project": project.name,
    }
    project_entities = list(project.entities.all())
    if len(project_entities) == 1:
        params["entity"] = project_entities[0].id
    return f"{base_url}?{urlencode(params)}"


def _get_project_permissions(user, project):
    permissions = {
        "can_access": False,
        "is_admin": False,
        "can_view_drafts": False,
    }
    if not user.is_authenticated:
        return permissions

    memberships = _get_memberships(user)
    if user.is_superuser or memberships.filter(role="ADMIN").exists():
        permissions.update(
            {
                "can_access": True,
                "is_admin": True,
                "can_view_drafts": True,
            }
        )
        return permissions

    project_entity_ids = set(project.entities.values_list("id", flat=True))
    has_global_scope = memberships.filter(entity__isnull=True).exists()
    has_entity_scope = bool(project_entity_ids) and memberships.filter(
        entity_id__in=project_entity_ids
    ).exists()
    permissions["can_access"] = has_global_scope or has_entity_scope

    if not permissions["can_access"]:
        return permissions

    permissions["can_view_drafts"] = memberships.filter(
        role__in=("LOADER", "VALIDATOR"),
        entity__isnull=True,
    ).exists() or (
        bool(project_entity_ids)
        and memberships.filter(
            role__in=("LOADER", "VALIDATOR"),
            entity_id__in=project_entity_ids,
        ).exists()
    )
    return permissions


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


def _extract_category_label(row, columns):
    for key in CATEGORY_LABEL_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            if isinstance(value, (date, datetime)):
                return value.strftime("%d/%m/%Y")
            return str(value).strip()
    for column in columns:
        if column.data_type not in ("STRING", "CHOICE", "DATE"):
            continue
        if column.name not in row:
            continue
        value = row.get(column.name)
        if value in (None, ""):
            continue
        if isinstance(value, (date, datetime)):
            return value.strftime("%d/%m/%Y")
        return str(value).strip()
    return None


def _extract_category_series_from_rows(rows, columns, candidate_keys):
    labels = []
    values = []
    positions = {}
    for row in rows:
        label = _extract_category_label(row, columns)
        value = _extract_row_value(row, columns, candidate_keys)
        if not label or value is None:
            continue
        if label in positions:
            values[positions[label]] = value
            continue
        positions[label] = len(labels)
        labels.append(label)
        values.append(value)
    return labels, values


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


def _text_to_lines(value):
    if value in (None, ""):
        return []
    lines = []
    text = str(value).replace("\r", "\n")
    for raw_line in text.split("\n"):
        cleaned = raw_line.strip()
        if not cleaned:
            continue
        cleaned = cleaned.lstrip("-*• ").strip()
        if cleaned:
            lines.append(cleaned)
    if lines:
        return lines
    cleaned = str(value).strip()
    return [cleaned] if cleaned else []


def _detect_report_variant(config, summary):
    configured_variant = config.normalized_report_variant()
    if configured_variant != ProjectReportConfig.VARIANT_AUTO:
        return configured_variant
    if any(
        summary.get(key)
        for key in ("company", "agreement_object", "addenda", "execution_term")
    ):
        return ProjectReportConfig.VARIANT_AGREEMENT
    name_pool = " ".join(
        filter(
            None,
            (
                getattr(config, "name", ""),
                getattr(config.project, "name", ""),
            ),
        )
    ).lower()
    if "convenio" in name_pool:
        return ProjectReportConfig.VARIANT_AGREEMENT
    return ProjectReportConfig.VARIANT_PROJECT


def _pick_year(request, fallback_year: int | None = None) -> int:
    year_param = (request.GET.get("year") or "").strip()
    if year_param.isdigit():
        year = int(year_param)
        if 2000 <= year <= 2100:
            return year
    if fallback_year:
        return fallback_year
    return timezone.now().year


@login_required
def project_list(request):
    if not _can_user_manage_projects(request.user):
        return redirect("home")

    is_admin = _is_admin_user(request.user)
    projects = Project.objects.prefetch_related("entities").select_related("created_by", "approved_by")
    if not is_admin:
        loader_entity_ids = _get_loader_entity_ids(request.user)
        projects = projects.filter(entities__id__in=loader_entity_ids).distinct()
    projects = list(projects.order_by("name"))

    editable_project_ids = set()
    for project in projects:
        project.schema_seed_url = _build_schema_seed_url(project)
        if not is_admin and _can_user_edit_project(request.user, project):
            editable_project_ids.add(project.id)

    return render(
        request,
        "projects/project_list.html",
        {
            "projects": projects,
            "is_admin": is_admin,
            "can_create_project": _can_user_create_projects(request.user),
            "editable_project_ids": editable_project_ids,
        },
    )


@login_required
def project_create(request):
    if not _can_user_create_projects(request.user):
        return redirect("projects:project_list")

    allowed_entity_ids = _get_loader_entity_ids(request.user)
    if request.method == "POST":
        form = ProjectForm(
            request.POST,
            user=request.user,
            allow_activation=False,
            allowed_entity_ids=allowed_entity_ids,
        )
        if form.is_valid():
            project = form.save(commit=False)
            project.workflow_status = Project.STATUS_PENDING
            project.workflow_comment = ""
            project.created_by = request.user
            project.approved_by = None
            project.approved_at = None
            project.is_active = False
            project.save()
            form.save_m2m()
            record_action(
                "OTHER",
                request=request,
                module="Projects",
                object_repr=f"Proyecto {project.name} registrado",
                details="Registrado por usuario operativo y enviado a aprobacion.",
            )
            return redirect("projects:project_list")
    else:
        form = ProjectForm(
            user=request.user,
            allow_activation=False,
            allowed_entity_ids=allowed_entity_ids,
        )
    return render(
        request,
        "projects/project_form.html",
        {
            "form": form,
            "project": None,
            "is_admin": False,
        },
    )


@login_required
def project_edit(request, pk: int):
    project = get_object_or_404(Project, pk=pk)
    if not _can_user_edit_project(request.user, project):
        return redirect("projects:project_list")

    allowed_entity_ids = _get_loader_entity_ids(request.user)
    if request.method == "POST":
        form = ProjectForm(
            request.POST,
            instance=project,
            user=request.user,
            allow_activation=False,
            allowed_entity_ids=allowed_entity_ids,
        )
        if form.is_valid():
            project = form.save(commit=False)
            project.workflow_status = Project.STATUS_PENDING
            project.workflow_comment = ""
            project.approved_by = None
            project.approved_at = None
            project.is_active = False
            project.save()
            form.save_m2m()
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
                    details=(
                        f"Campos: {', '.join(changed)}. Justificacion: {justification}. "
                        "Reenviado a aprobacion."
                    ),
                )
            return redirect("projects:project_list")
    else:
        form = ProjectForm(
            instance=project,
            user=request.user,
            allow_activation=False,
            allowed_entity_ids=allowed_entity_ids,
        )
    return render(
        request,
        "projects/project_form.html",
        {
            "form": form,
            "project": project,
            "is_admin": False,
        },
    )


@login_required
def project_delete(request, pk: int):
    project = get_object_or_404(Project, pk=pk)
    if not _can_user_edit_project(request.user, project):
        return redirect("projects:project_list")
    if request.method == "POST":
        project_name = project.name
        project.delete()
        record_action(
            "OTHER",
            request=request,
            module="Projects",
            object_repr=f"Proyecto {project_name} eliminado",
            details="Eliminado por usuario operativo antes de aprobacion.",
        )
        return redirect("projects:project_list")
    return render(
        request,
        "projects/project_confirm_delete.html",
        {"project": project, "is_admin": False},
    )


@admin_role_required
def project_review(request, pk: int, decision: str):
    project = get_object_or_404(Project, pk=pk)
    if decision not in {"approve", "reject"}:
        return redirect("projects:project_list")

    if request.method == "POST":
        if decision == "approve":
            project.workflow_status = Project.STATUS_APPROVED
            project.is_active = True
            project.workflow_comment = ""
            project.approved_by = request.user
            project.approved_at = timezone.now()
            detail = "Proyecto aprobado por administracion."
            object_repr = f"Proyecto {project.name} aprobado"
        else:
            project.workflow_status = Project.STATUS_REJECTED
            project.is_active = False
            project.approved_by = request.user
            project.approved_at = None
            project.workflow_comment = "Requiere ajustes antes de su aprobacion."
            detail = "Proyecto rechazado por administracion."
            object_repr = f"Proyecto {project.name} rechazado"
        project.save(
            update_fields=[
                "workflow_status",
                "is_active",
                "workflow_comment",
                "approved_by",
                "approved_at",
                "updated_at",
            ]
        )
        record_action(
            "OTHER",
            request=request,
            module="Projects",
            object_repr=object_repr,
            details=detail,
        )
    return redirect("projects:project_list")


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
    ).prefetch_related("project__entities").filter(
        is_active=True,
        project__is_active=True,
        project__workflow_status=Project.STATUS_APPROVED,
    )

    memberships = _get_memberships(user)
    is_admin = user.is_superuser or memberships.filter(role="ADMIN").exists()
    if not is_admin:
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
        project__is_active=True,
        project__workflow_status=Project.STATUS_APPROVED,
    )

    permissions = _get_project_permissions(request.user, config.project)
    if not permissions["can_access"]:
        return render(request, "projects/report_denied.html", {"config": config})

    can_see_drafts = permissions["can_view_drafts"]

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

    project_entity_ids = list(config.project.entities.values_list("id", flat=True))
    summary_qs = DatasetInstance.objects.filter(dataset_type=config.report_dataset)
    program_qs = DatasetInstance.objects.filter(dataset_type=config.curve_program_dataset)
    executed_qs = DatasetInstance.objects.filter(dataset_type=config.curve_executed_dataset)
    if project_entity_ids:
        summary_qs = summary_qs.filter(entity_id__in=project_entity_ids)
        program_qs = program_qs.filter(entity_id__in=project_entity_ids)
        executed_qs = executed_qs.filter(entity_id__in=project_entity_ids)
    else:
        summary_qs = summary_qs.none()
        program_qs = program_qs.none()
        executed_qs = executed_qs.none()

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
            executed_week_options.append(
                {
                    "id": inst.id,
                    "label": label,
                    "date": f"{inst.period:%d/%m/%Y}",
                }
            )

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
        "company": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["company"], None
        ),
        "location": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["location"], config.project.location
        ),
        "executor": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["executor"], config.project.executor
        ),
        "description": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["description"], config.project.description
        ),
        "agreement_object": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["agreement_object"], None
        ),
        "budget_mmbs": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["budget_mmbs"], config.project.budget_mmbs
        ),
        "subscription_date": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["subscription_date"], None
        ),
        "addenda": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["addenda"], None
        ),
        "execution_term": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["execution_term"], None
        ),
        "start_date": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["start_date"], config.project.start_date
        ),
        "end_date": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["end_date"], config.project.end_date
        ),
        "stage": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["stage"], config.project.stage or None
        ),
        "planned_pct": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["planned_pct"], None
        ),
        "executed_pct": _resolve_summary_value(
            summary_row, SUMMARY_ALIASES["executed_pct"], None
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
    program_rows = _load_instance_rows(program_instance, program_columns)
    configured_report_variant = config.normalized_report_variant()
    report_variant = _detect_report_variant(config, summary)
    supported_variants = {
        ProjectReportConfig.VARIANT_PROJECT,
        ProjectReportConfig.VARIANT_AGREEMENT,
    }
    render_variant = (
        report_variant if report_variant in supported_variants else ProjectReportConfig.VARIANT_PROJECT
    )

    chart_kind = "line"
    chart_labels = list(MONTH_LABELS)
    program_values = [None] * len(chart_labels)
    executed_values = [None] * len(chart_labels)

    def populate_month_series(rows, columns, candidate_keys, values):
        month_map = _extract_month_values_from_rows(rows)
        if month_map:
            for month, value in month_map.items():
                values[month - 1] = value
            return True
        populated = False
        for row in rows:
            month_value = None
            for key in MONTH_KEYS:
                if key in row:
                    month_value = _parse_month(row.get(key))
                    if month_value:
                        break
            if not month_value:
                continue
            value = _extract_row_value(row, columns, candidate_keys)
            if value is not None:
                values[month_value - 1] = value
                populated = True
        return populated

    populate_month_series(program_rows, program_columns, PROGRAM_VALUE_KEYS, program_values)

    executed_category_rows = []
    if executed_frequency == DatasetType.WEEKLY and selected_executed_instance:
        rows = _load_instance_rows(selected_executed_instance, executed_columns)
        executed_category_rows = rows
        populate_month_series(rows, executed_columns, EXECUTED_VALUE_KEYS, executed_values)
    elif executed_instances:
        latest_executed = executed_instances[-1]
        wide_rows = _load_instance_rows(latest_executed, executed_columns)
        executed_category_rows = wide_rows
        if not populate_month_series(wide_rows, executed_columns, EXECUTED_VALUE_KEYS, executed_values):
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

    if render_variant == ProjectReportConfig.VARIANT_AGREEMENT:
        program_category_labels, program_category_values = _extract_category_series_from_rows(
            program_rows,
            program_columns,
            PROGRAM_VALUE_KEYS,
        )
        executed_category_labels, executed_category_values = _extract_category_series_from_rows(
            executed_category_rows,
            executed_columns,
            EXECUTED_VALUE_KEYS,
        )
        category_labels = []
        for label in program_category_labels + executed_category_labels:
            if label not in category_labels:
                category_labels.append(label)
        if category_labels:
            program_map = dict(zip(program_category_labels, program_category_values))
            executed_map = dict(zip(executed_category_labels, executed_category_values))
            chart_kind = "bar"
            chart_labels = category_labels
            program_values = [program_map.get(label) for label in chart_labels]
            executed_values = [executed_map.get(label) for label in chart_labels]
        elif summary["planned_pct"] is not None or summary["executed_pct"] is not None:
            chart_kind = "bar"
            chart_labels = ["Avance actual"]
            program_values = [summary["planned_pct"]]
            executed_values = [summary["executed_pct"]]

    report_date = summary.get("report_date")
    if isinstance(report_date, datetime):
        report_date = report_date.date()

    context = {
        "config": config,
        "project": config.project,
        "summary": summary,
        "summary_instance": summary_instance,
        "report_variant": render_variant,
        "configured_report_variant": configured_report_variant,
        "detected_report_variant": report_variant,
        "report_date": report_date,
        "year": year,
        "chart_kind": chart_kind,
        "chart_labels": chart_labels,
        "program_values": program_values,
        "executed_values": executed_values,
        "source": source,
        "can_see_drafts": can_see_drafts,
        "executed_week_options": executed_week_options,
        "selected_week_id": selected_week_id,
        "status_lines": _text_to_lines(summary.get("status")),
        "justification_lines": _text_to_lines(summary.get("justification")),
        "actions_lines": _text_to_lines(summary.get("actions")),
        "description_lines": _text_to_lines(summary.get("description")),
        "agreement_object_lines": _text_to_lines(summary.get("agreement_object")),
        "location_lines": _text_to_lines(summary.get("location")),
    }

    return render(request, "projects/report_detail.html", context)
