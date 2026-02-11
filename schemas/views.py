from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.forms import inlineformset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import admin_required
from accounts.models import Membership
from audit.utils import record_action

from .forms import CertificationSchemaForm, ColumnDefForm, DatasetTypeForm
from .models import ColumnDef, DatasetType
from .services import consolidate_latest_month


def _is_admin_user(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()


def _dataset_scope_label(dataset: DatasetType) -> str:
    return dataset.entity.code or dataset.entity.name


def _dataset_scope_filter(dataset: DatasetType) -> Q:
    return Q(entity=dataset.entity)



def _entity_hierarchy(entity):
    if not entity:
        return None
    category = getattr(entity, "category", None)
    subsector = getattr(category, "subsector", None) if category else None
    sector = getattr(subsector, "sector", None) if subsector else None
    return {
        "sector": sector,
        "subsector": subsector,
        "category": category,
        "entity": entity,
    }

def schema_list(request):
    user = request.user
    is_admin = _is_admin_user(user)

    datasets = DatasetType.objects.select_related("entity__category__subsector__sector").order_by(
        "entity__name",
        "name",
        "-version",
    )

    if not is_admin:
        datasets = datasets.filter(is_certification=False)

        if user.is_authenticated:
            loader_memberships = Membership.objects.filter(
                user=user, role="LOADER", is_active=True
            )
            has_global_loader = loader_memberships.filter(entity__isnull=True).exists()
            if not has_global_loader:
                allowed_entities = list(
                    loader_memberships.exclude(entity__isnull=True).values_list(
                        "entity_id", flat=True
                    )
                )
                if allowed_entities:
                    datasets = datasets.filter(entity_id__in=allowed_entities)
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
    qs = DatasetType.objects.select_related("entity__category__subsector__sector")
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
    dataset = _get_dataset_by_slug_or_pk(slug) if slug else None

    is_admin = _is_admin_user(request.user)
    if is_admin and dataset and not dataset.is_certification:
        return redirect("schemas:schema_detail", slug=dataset.slug)

    loader_entity = None
    loader_scope_items = []
    allowed_entities_qs = None
    allowed_entity_ids: list[int] = []
    has_global_loader = False

    if not is_admin:
        if not request.user.is_authenticated:
            return redirect("login")

        loader_memberships = (
            Membership.objects.filter(user=request.user, role="LOADER", is_active=True)
            .select_related("entity__category__subsector__sector")
            .order_by("id")
        )
        if not loader_memberships.exists():
            return redirect("schemas:schema_list")

        has_global_loader = any(m.entity_id is None for m in loader_memberships)
        allowed_entity_ids = [m.entity_id for m in loader_memberships if m.entity_id]

        from structure.models import Entity

        if has_global_loader:
            allowed_entities_qs = Entity.objects.filter(is_active=True).order_by("name")
        else:
            allowed_entities_qs = Entity.objects.filter(
                id__in=allowed_entity_ids,
                is_active=True,
            ).order_by("name")

        loader_entity = next((m.entity for m in loader_memberships if m.entity_id), None)

        seen_entities = set()
        for membership in loader_memberships:
            if not membership.entity_id or membership.entity_id in seen_entities:
                continue
            seen_entities.add(membership.entity_id)
            hierarchy = _entity_hierarchy(membership.entity)
            if hierarchy:
                loader_scope_items.append(hierarchy)

        if dataset and not has_global_loader and dataset.entity_id not in allowed_entity_ids:
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
            allowed_entities_qs=allowed_entities_qs,
            allow_set_active=is_admin,
        )
        formset = DatasetColumnFormSet(request.POST, instance=dataset)

        if form.is_valid() and formset.is_valid():
            dataset = form.save(commit=False)
            if not is_admin:
                dataset.is_certification = False
                dataset.source_dataset = None
                if not has_global_loader and loader_entity:
                    dataset.entity = loader_entity
                elif not dataset.entity_id and loader_entity:
                    dataset.entity = loader_entity
                if not has_global_loader and dataset.entity_id not in allowed_entity_ids:
                    return redirect("schemas:schema_list")
                dataset.status = DatasetType.STATUS_DRAFT
                dataset.is_active = False

            dataset.save()
            formset.instance = dataset
            formset.save()

            verb = "creado" if slug is None else "editado"
            record_action(
                "SCHEMA",
                request=request,
                module="Schemas",
                object_repr=f"Esquema {dataset.name} v{dataset.version} ({_dataset_scope_label(dataset)}) {verb}",
                details=(
                    "Esquema de certificacion mensual"
                    if dataset.is_certification
                    else f"Esquema de datos ({dataset.get_validation_frequency_display()})"
                ),
            )
            return redirect(reverse("schemas:schema_detail", args=[dataset.slug]))
    else:
        form = DatasetTypeForm(
            instance=dataset,
            allowed_entities_qs=allowed_entities_qs,
            allow_set_active=is_admin,
        )
        if not is_admin and not dataset and loader_entity:
            form.fields["entity"].initial = loader_entity
        formset = DatasetColumnFormSet(instance=dataset)

    return render(
        request,
        "schemas/schema_edit.html",
        {
            "form": form,
            "formset": formset,
            "dataset": dataset,
            "loader_entity": loader_entity,
            "loader_scope_items": loader_scope_items,
            "dataset_scope": _entity_hierarchy(dataset.entity) if dataset and dataset.entity_id else None,
            "has_global_loader": has_global_loader,
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
        | Q(entity__isnull=True)
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
        | Q(entity__isnull=True)
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
                "enviado a aprobacion"
            ),
            details="Envio de borrador a aprobacion de admin",
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
        details="Aprobacion de esquema por administracion",
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
        details=comment or "Rechazo de esquema por administracion",
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
                DatasetType.objects.filter(entity=source.entity, name=name)
                .aggregate(max_version=Max("version"))
            )
            next_version = (current_max["max_version"] or 0) + 1

            dataset = DatasetType.objects.create(
                entity=source.entity,
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
                    f"Esquema certificacion {dataset.name} v{dataset.version} "
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

