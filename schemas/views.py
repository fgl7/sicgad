from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.forms import inlineformset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import admin_required
from django.utils import timezone

from accounts.models import Membership
from plants.models import Plant
from projects.models import Project
from audit.utils import record_action

from .models import ColumnDef, DatasetType
from .forms import DatasetTypeForm, ColumnDefForm, CertificationSchemaForm
from .services import consolidate_latest_month


def _is_admin_user(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()


def _dataset_scope_label(dataset: DatasetType) -> str:
    if dataset.plant:
        return dataset.plant.code
    if dataset.project:
        return dataset.project.code or dataset.project.name
    return "SIN-DESTINO"


def _dataset_scope_filter(dataset: DatasetType) -> Q:
    if dataset.plant:
        return Q(plant=dataset.plant)
    if dataset.project:
        return Q(project=dataset.project)
    return Q(pk__in=[])


def schema_list(request):
    user = request.user
    is_admin = _is_admin_user(user)

    datasets = DatasetType.objects.select_related("plant", "project").order_by(
        "plant__code",
        "project__name",
        "name",
        "-version",
    )

    if not is_admin:
        datasets = datasets.filter(is_certification=False)

        if user.is_authenticated:
            loader_memberships = Membership.objects.filter(
                user=user, role="LOADER", is_active=True
            )
            has_global_loader = loader_memberships.filter(
                plant__isnull=True, project__isnull=True
            ).exists()
            if not has_global_loader:
                allowed_plants = list(
                    loader_memberships.exclude(plant__isnull=True).values_list(
                        "plant_id", flat=True
                    )
                )
                allowed_projects = list(
                    loader_memberships.exclude(project__isnull=True).values_list(
                        "project_id", flat=True
                    )
                )
                if allowed_plants or allowed_projects:
                    datasets = datasets.filter(
                        Q(plant_id__in=allowed_plants) | Q(project_id__in=allowed_projects)
                    )
                else:
                    datasets = datasets.none()

    can_edit_schemas = False
    can_create_schemas = False
    if user.is_authenticated and not is_admin:
        is_loader = Membership.objects.filter(user=user, role="LOADER", is_active=True).exists()
        if is_loader:
            can_edit_schemas = True
            can_create_schemas = True

    return render(
        request,
        "schemas/schema_list.html",
        {
            "datasets": datasets,
            "can_edit_schemas": can_edit_schemas,
            "can_create_schemas": can_create_schemas,
        },
    )


def _get_dataset_by_slug_or_pk(slug: str) -> DatasetType:
    qs = DatasetType.objects.select_related("plant")
    try:
        return qs.get(slug=slug)
    except DatasetType.DoesNotExist:
        try:
            pk = int(slug)
        except (TypeError, ValueError):
            raise Http404
        return get_object_or_404(qs, pk=pk)


def schema_detail(request, slug):
    dataset = _get_dataset_by_slug_or_pk(slug)
    columns = dataset.columns.order_by("display_order", "name")

    user = request.user
    is_admin = _is_admin_user(user)
    can_edit_schemas = False
    if user.is_authenticated and not is_admin:
        is_loader = Membership.objects.filter(user=user, role="LOADER", is_active=True).exists()
        if is_loader:
            can_edit_schemas = True

    return render(
        request,
        "schemas/schema_detail.html",
        {
            "dataset": dataset,
            "columns": columns,
            "can_edit_schemas": can_edit_schemas,
            "is_admin": is_admin,
        },
    )


def schema_edit(request, slug=None):
    if slug:
        dataset = _get_dataset_by_slug_or_pk(slug)
    else:
        dataset = None

    is_admin = _is_admin_user(request.user)
    if is_admin and dataset and not dataset.is_certification:
        return redirect("schemas:schema_detail", slug=dataset.slug)
    loader_plant = None
    loader_project = None
    allowed_plants_qs = None
    allowed_projects_qs = None
    allowed_plant_ids: list[int] = []
    allowed_project_ids: list[int] = []
    has_global_loader = False
    if not is_admin:
        if not request.user.is_authenticated:
            return redirect("login")

        loader_memberships = (
            Membership.objects.filter(user=request.user, role="LOADER", is_active=True)
            .select_related("plant", "project")
            .order_by("id")
        )
        if not loader_memberships.exists():
            return redirect("schemas:schema_list")

        has_global_loader = any(
            m.plant_id is None and m.project_id is None for m in loader_memberships
        )
        allowed_plant_ids = [m.plant_id for m in loader_memberships if m.plant_id]
        allowed_project_ids = [m.project_id for m in loader_memberships if m.project_id]
        allowed_plants_qs = (
            Plant.objects.all().order_by("code")
            if has_global_loader
            else Plant.objects.filter(id__in=allowed_plant_ids).order_by("code")
        )
        allowed_projects_qs = (
            Project.objects.all().order_by("name")
            if has_global_loader
            else Project.objects.filter(id__in=allowed_project_ids).order_by("name")
        )
        loader_plant = next((m.plant for m in loader_memberships if m.plant_id), None)
        loader_project = next((m.project for m in loader_memberships if m.project_id), None)
        if dataset and not has_global_loader:
            if dataset.plant_id and dataset.plant_id not in allowed_plant_ids:
                return redirect("schemas:schema_list")
            if dataset.project_id and dataset.project_id not in allowed_project_ids:
                return redirect("schemas:schema_list")

    DatasetColumnFormSet = inlineformset_factory(
        DatasetType,
        ColumnDef,
        form=ColumnDefForm,
        extra=1,
        can_delete=True,
    )

    if request.method == "POST":
        form = DatasetTypeForm(
            request.POST,
            instance=dataset,
            allowed_plants_qs=allowed_plants_qs,
            allowed_projects_qs=allowed_projects_qs,
            allow_set_active=is_admin,
        )
        formset = DatasetColumnFormSet(request.POST, instance=dataset)
        if form.is_valid() and formset.is_valid():
            dataset = form.save(commit=False)
            if not is_admin:
                dataset.is_certification = False
                dataset.source_dataset = None
                if not dataset.plant_id and not dataset.project_id:
                    if loader_plant:
                        dataset.plant = loader_plant
                    elif loader_project:
                        dataset.project = loader_project
                if (
                    not has_global_loader
                    and dataset.plant_id
                    and dataset.plant_id not in allowed_plant_ids
                ):
                    return redirect("schemas:schema_list")
                if (
                    not has_global_loader
                    and dataset.project_id
                    and dataset.project_id not in allowed_project_ids
                ):
                    return redirect("schemas:schema_list")
                dataset.status = DatasetType.STATUS_DRAFT
                dataset.is_active = False
            dataset.save()
            formset.instance = dataset
            formset.save()
            action = "SCHEMA"
            verb = "creado" if slug is None else "editado"
            record_action(
                action,
                request=request,
                module="Schemas",
                object_repr=(
                    f"Esquema {dataset.name} v{dataset.version} ({_dataset_scope_label(dataset)}) {verb}"
                ),
                details=(
                    "Esquema de certificación mensual"
                    if dataset.is_certification
                    else f"Esquema de datos ({dataset.get_validation_frequency_display()})"
                ),
            )
            return redirect(reverse("schemas:schema_detail", args=[dataset.slug]))
    else:
        form = DatasetTypeForm(
            instance=dataset,
            allowed_plants_qs=allowed_plants_qs,
            allowed_projects_qs=allowed_projects_qs,
            allow_set_active=is_admin,
        )
        if not is_admin and not dataset:
            if loader_plant:
                form.fields["plant"].initial = loader_plant
            if loader_project:
                form.fields["project"].initial = loader_project
        formset = DatasetColumnFormSet(instance=dataset)

    return render(
        request,
        "schemas/schema_edit.html",
        {
            "form": form,
            "formset": formset,
            "dataset": dataset,
            "loader_plant": loader_plant,
            "loader_project": loader_project,
            "is_admin": is_admin,
        },
    )


@login_required
def schema_delete(request, slug):
    if request.method != "POST":
        return redirect("schemas:schema_list")

    dataset = _get_dataset_by_slug_or_pk(slug)
    user = request.user

    if _is_admin_user(user) or dataset.is_certification:
        return redirect("schemas:schema_list")

    can_delete = Membership.objects.filter(
        user=user,
        role="LOADER",
        is_active=True,
    ).filter(
        _dataset_scope_filter(dataset)
        | Q(plant__isnull=True, project__isnull=True)
    ).exists()

    if not can_delete or dataset.status != DatasetType.STATUS_DRAFT:
        messages.info(
            request,
            "Solo puedes eliminar esquemas en borrador que aun no fueron enviados a aprobacion.",
        )
        return redirect("schemas:schema_list")

    if dataset.instances.exists():
        messages.error(
            request,
            "No se puede eliminar un esquema que ya tiene cargas asociadas.",
        )
        return redirect("schemas:schema_list")

    scope_label = _dataset_scope_label(dataset)
    dataset_name = dataset.name
    dataset_version = dataset.version
    dataset.delete()

    record_action(
        "SCHEMA",
        request=request,
        module="Schemas",
        object_repr=f"Esquema {dataset_name} v{dataset_version} ({scope_label}) eliminado",
        details="Eliminado por cargador antes de aprobacion.",
    )
    messages.success(request, "Esquema eliminado correctamente.")
    return redirect("schemas:schema_list")


@admin_required
def schema_toggle_one_time(request, slug):
    if request.method != "POST":
        return redirect("schemas:schema_detail", slug=slug)

    dataset = _get_dataset_by_slug_or_pk(slug)
    dataset.is_one_time = not dataset.is_one_time
    dataset.save(update_fields=["is_one_time"])

    record_action(
        "SCHEMA",
        request=request,
        module="Schemas",
        object_repr=(
            f"Esquema {dataset.name} v{dataset.version} ({_dataset_scope_label(dataset)}) "
            f"{'marcado' if dataset.is_one_time else 'desmarcado'} como carga unica"
        ),
        details="Cambio de bandera de carga unica por administracion.",
    )
    messages.success(
        request,
        "Actualizado: esquema marcado como carga unica."
        if dataset.is_one_time
        else "Actualizado: esquema habilitado para multiples cargas.",
    )
    return redirect("schemas:schema_detail", slug=dataset.slug or dataset.pk)


def schema_submit_for_approval(request, slug):
    if request.method != "POST":
        return redirect("schemas:schema_list")

    dataset = _get_dataset_by_slug_or_pk(slug)

    is_admin = _is_admin_user(request.user)
    if not request.user.is_authenticated or is_admin:
        return redirect("schemas:schema_list")

    can_submit = Membership.objects.filter(
        user=request.user,
        role="LOADER",
        is_active=True,
    ).filter(
        _dataset_scope_filter(dataset)
        | Q(plant__isnull=True, project__isnull=True)
    ).exists()
    if not can_submit:
        return redirect("schemas:schema_list")

    if dataset.status == DatasetType.STATUS_DRAFT:
        dataset.status = DatasetType.STATUS_PENDING
        dataset.is_active = False
        dataset.save(update_fields=["status", "is_active", "updated_at"])
        record_action(
            "SCHEMA",
            request=request,
            module="Schemas",
            object_repr=(
                f"Esquema {dataset.name} v{dataset.version} ({_dataset_scope_label(dataset)}) "
                "enviado a aprobación"
            ),
            details="Envío de borrador a aprobación de admin",
        )

    return redirect("schemas:schema_list")


@admin_required
def schema_approve(request, slug):
    if request.method != "POST":
        return redirect("schemas:schema_list")

    dataset = _get_dataset_by_slug_or_pk(slug)

    dataset.status = DatasetType.STATUS_APPROVED
    dataset.is_active = True
    dataset.status_comment = ""
    dataset.save(update_fields=["status", "is_active", "status_comment", "updated_at"])
    record_action(
        "SCHEMA",
        request=request,
        module="Schemas",
        object_repr=(
            f"Esquema {dataset.name} v{dataset.version} ({_dataset_scope_label(dataset)}) aprobado"
        ),
        details="Aprobación de esquema por administración",
    )

    return redirect("schemas:schema_list")


@admin_required
def schema_reject(request, slug):
    if request.method != "POST":
        return redirect("schemas:schema_list")

    dataset = _get_dataset_by_slug_or_pk(slug)

    comment = request.POST.get("comment", "").strip()
    dataset.status = DatasetType.STATUS_REJECTED
    dataset.is_active = False
    dataset.status_comment = comment
    dataset.save(update_fields=["status", "is_active", "status_comment", "updated_at"])
    record_action(
        "SCHEMA",
        request=request,
        module="Schemas",
        object_repr=(
            f"Esquema {dataset.name} v{dataset.version} ({_dataset_scope_label(dataset)}) rechazado"
        ),
        details=comment or "Rechazo de esquema por administración",
    )

    return redirect("schemas:schema_list")


@admin_required
def certification_schema_create(request):
    if request.method == "POST":
        form = CertificationSchemaForm(request.POST)
        if form.is_valid():
            source = form.cleaned_data["source_dataset"]
            name = form.cleaned_data["name"]
            columns = form.cleaned_data["columns"]

            current_max = (
                DatasetType.objects.filter(plant=source.plant, name=name)
                .aggregate(max_version=Max("version"))
            )
            next_version = (current_max["max_version"] or 0) + 1

            dataset = DatasetType.objects.create(
                plant=source.plant,
                name=name,
                version=next_version,
                validation_frequency=DatasetType.MONTHLY,
                is_certification=True,
                is_active=True,
                source_dataset=source,
            )

            for col in columns:
                ColumnDef.objects.create(
                    dataset_type=dataset,
                    name=col.name,
                    label=col.label,
                    data_type=col.data_type,
                    required=col.required,
                    min_value=col.min_value,
                    max_value=col.max_value,
                    regex=col.regex,
                    choices_raw=col.choices_raw,
                    unit=col.unit,
                    axis_role=col.axis_role,
                    default_agg=col.default_agg,
                    is_primary_kpi=col.is_primary_kpi,
                    display_order=col.display_order,
                    is_active=col.is_active,
                )

            consolidate_latest_month(dataset, request=request)

            record_action(
                "SCHEMA",
                request=request,
                module="Schemas",
                object_repr=(
                    f"Esquema certificación {dataset.name} v{dataset.version} "
                    f"({_dataset_scope_label(dataset)}) creado"
                ),
                details=f"Derivado de {source.name} v{source.version}",
            )
            return redirect(reverse("schemas:schema_detail", args=[dataset.slug]))
    else:
        initial = {}
        selected_dataset = request.GET.get("source_dataset")
        if selected_dataset:
            initial["source_dataset"] = selected_dataset
        form = CertificationSchemaForm(initial=initial)

    return render(
        request,
        "schemas/certification_schema_create.html",
        {
            "form": form,
        },
    )
