from django.db.models import Max, Q
from django.forms import inlineformset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import admin_required
from django.utils import timezone

from accounts.models import Membership
from plants.models import Plant
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


def schema_list(request):
    user = request.user
    is_admin = _is_admin_user(user)

    datasets = DatasetType.objects.select_related("plant").order_by("plant__code", "name", "-version")

    if not is_admin:
        datasets = datasets.filter(is_certification=False)

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
    allowed_plants_qs = None
    allowed_plant_ids: list[int] = []
    has_global_loader = False
    if not is_admin:
        if not request.user.is_authenticated:
            return redirect("login")

        loader_memberships = (
            Membership.objects.filter(user=request.user, role="LOADER", is_active=True)
            .select_related("plant")
            .order_by("id")
        )
        if not loader_memberships.exists():
            return redirect("schemas:schema_list")

        has_global_loader = any(m.plant_id is None for m in loader_memberships)
        allowed_plant_ids = [m.plant_id for m in loader_memberships if m.plant_id]
        allowed_plants_qs = (
            Plant.objects.all().order_by("code")
            if has_global_loader
            else Plant.objects.filter(id__in=allowed_plant_ids).order_by("code")
        )
        loader_plant = next((m.plant for m in loader_memberships if m.plant_id), None)
        if dataset and not has_global_loader and dataset.plant_id not in allowed_plant_ids:
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
            allow_set_active=is_admin,
        )
        formset = DatasetColumnFormSet(request.POST, instance=dataset)
        if form.is_valid() and formset.is_valid():
            dataset = form.save(commit=False)
            if not is_admin:
                dataset.is_certification = False
                dataset.source_dataset = None
                if loader_plant and not dataset.plant_id:
                    dataset.plant = loader_plant
                if (
                    not has_global_loader
                    and dataset.plant_id
                    and dataset.plant_id not in allowed_plant_ids
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
                object_repr=f"Esquema {dataset.name} v{dataset.version} ({dataset.plant.code}) {verb}",
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
            allow_set_active=is_admin,
        )
        if not is_admin and loader_plant and not dataset:
            form.fields["plant"].initial = loader_plant
        formset = DatasetColumnFormSet(instance=dataset)

    return render(
        request,
        "schemas/schema_edit.html",
        {
            "form": form,
            "formset": formset,
            "dataset": dataset,
            "loader_plant": loader_plant,
            "is_admin": is_admin,
        },
    )


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
    ).filter(Q(plant=dataset.plant) | Q(plant__isnull=True)).exists()
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
            object_repr=f"Esquema {dataset.name} v{dataset.version} ({dataset.plant.code}) enviado a aprobación",
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
        object_repr=f"Esquema {dataset.name} v{dataset.version} ({dataset.plant.code}) aprobado",
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
        object_repr=f"Esquema {dataset.name} v{dataset.version} ({dataset.plant.code}) rechazado",
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
                object_repr=f"Esquema certificación {dataset.name} v{dataset.version} ({dataset.plant.code}) creado",
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
