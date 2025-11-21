from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.db.models import Q
from io import BytesIO, TextIOWrapper
import csv
import openpyxl

from accounts.models import Membership
from schemas.models import DatasetType
from audit.utils import record_action
from .forms import DatasetInstanceUploadForm, DatasetInstanceEditForm
from .models import DatasetInstance


def upload(request):
    user = request.user
    if user.is_authenticated and (
        user.is_superuser
        or Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()
    ):
        messages.info(
            request,
            "Los administradores no realizan cargas directas; use el historial para revisar y gestionar cargas existentes.",
        )
        return redirect(reverse("ingest:upload_history"))

    if request.method == "POST":
        form = DatasetInstanceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            instance: DatasetInstance = form.save(commit=False)

            if request.user.is_authenticated:
                membership = (
                    Membership.objects.filter(user=request.user, plant=instance.plant, is_active=True)
                    .order_by("role")
                    .first()
                )
            else:
                membership = None

            instance.created_by = membership
            instance.state = DatasetInstance.STATE_DRAFT
            instance.row_count = 0
            instance.error_count = 0
            instance.last_error_summary = ""
            instance.save()

            messages.success(
                request,
                "Archivo subido correctamente. Revisa tus cargas y envía el dataset a validación diaria.",
            )
            record_action(
                "UPLOAD",
                request=request,
                module="Ingest",
                object_repr=f"{instance.dataset_type.name} | {instance.period}",
                details=f"Planta {instance.plant.code}",
            )
            return redirect(reverse("ingest:upload_history"))
    else:
        form = DatasetInstanceUploadForm()

    if request.user.is_authenticated:
        instances = (
            DatasetInstance.objects.select_related("dataset_type", "plant")
            .filter(created_by__user=request.user)
            .order_by("-created_at")[:10]
        )
    else:
        instances = DatasetInstance.objects.none()

    return render(request, "ingest/upload.html", {"form": form, "instances": instances})


def download_template(request):
    dataset_type_id = request.GET.get("dataset_type")
    if not dataset_type_id:
        return redirect("ingest:upload")

    try:
        ds = DatasetType.objects.get(
            pk=dataset_type_id,
            is_active=True,
            status=DatasetType.STATUS_APPROVED,
        )
    except DatasetType.DoesNotExist:
        raise Http404("Dataset no encontrado o no aprobado.")

    columns = ds.columns.filter(is_active=True).order_by("display_order", "name")

    if not columns.exists():
        raise Http404("El esquema seleccionado no tiene columnas activas.")

    base_name = f"plantilla_{ds.plant.code}_{ds.name}"
    safe_name = f"{slugify(base_name) or 'plantilla'}.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plantilla"

    header = [col.label or col.name for col in columns]
    ws.append(header)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename=\"{safe_name}\"'

    return response


def instance_detail(request, pk):
    instance = (
        DatasetInstance.objects.select_related("dataset_type", "plant", "created_by__user")
        .filter(pk=pk)
        .first()
    )
    if not instance:
        raise Http404("Carga no encontrada.")

    user = request.user
    if not user.is_authenticated:
        return redirect("ingest:upload_history")

    is_admin = user.is_superuser or Membership.objects.filter(
        user=user,
        role="ADMIN",
        is_active=True,
    ).exists()

    is_creator = instance.created_by and instance.created_by.user_id == user.id

    is_validator = (
        Membership.objects.filter(
            user=user,
            role="VALIDATOR",
            is_active=True,
        )
        .filter(Q(plant=instance.plant) | Q(plant__isnull=True))
        .exists()
    )

    is_loader = Membership.objects.filter(
        user=user,
        role="LOADER",
        is_active=True,
        plant=instance.plant,
    ).exists()

    if not (is_admin or is_creator or is_validator):
        return redirect("ingest:upload_history")

    header = []
    rows = []

    if instance.raw_file:
        file_field = instance.raw_file
        name = file_field.name or ""
        ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""

        try:
            if ext in ("xlsx", "xlsm", "xltx", "xltm"):
                with file_field.open("rb") as fh:
                    wb = openpyxl.load_workbook(fh, read_only=True, data_only=True)
                    ws = wb.active
                    for i, row in enumerate(ws.iter_rows(values_only=True)):
                        values = ["" if v is None else str(v) for v in row]
                        if i == 0:
                            header = values
                        else:
                            rows.append(values)
                        if len(rows) >= 100:
                            break
            else:
                with file_field.open("rb") as fh:
                    wrapper = TextIOWrapper(fh, encoding="utf-8", errors="ignore")
                    reader = csv.reader(wrapper)
                    for i, row in enumerate(reader):
                        values = row
                        if i == 0:
                            header = values
                        else:
                            rows.append(values)
                        if len(rows) >= 100:
                            break
        except Exception:
            header = []
            rows = []

    next_url = request.GET.get("next")
    if next_url and next_url.startswith("/"):
        back_url = next_url
    elif is_loader and not is_validator and not is_admin:
        back_url = reverse("ingest:upload")
    elif is_validator and not is_admin:
        # Validador (con o sin rol de cargador): volver al detalle de validación
        back_url = reverse("validation:detail", args=[instance.pk])
    elif is_admin:
        back_url = reverse("validation:admin_overview")
    else:
        back_url = reverse("ingest:upload_history")

    return render(
        request,
        "ingest/instance_detail.html",
        {
            "instance": instance,
            "header": header,
            "rows": rows,
            "back_url": back_url,
        },
    )


def upload_history(request):
    if request.user.is_authenticated:
        queryset = DatasetInstance.objects.select_related("dataset_type", "plant", "created_by__user")

        if request.user.is_superuser or Membership.objects.filter(
            user=request.user,
            role="ADMIN",
            is_active=True,
        ).exists():
            instances = queryset.order_by("-created_at")[:100]
        else:
            instances = queryset.filter(created_by__user=request.user).order_by("-created_at")[:50]
    else:
        instances = DatasetInstance.objects.none()

    is_validator = (
        Membership.objects.filter(
            user=request.user,
            role="VALIDATOR",
            is_active=True,
        ).exists()
        if request.user.is_authenticated
        else False
    )
    is_admin = (
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or Membership.objects.filter(
                user=request.user,
                role="ADMIN",
                is_active=True,
            ).exists()
        )
    )

    return render(
        request,
        "ingest/upload_history.html",
        {
            "instances": instances,
            "is_validator": is_validator,
            "is_admin": is_admin,
        },
    )


def submit_instance(request, pk):
    if request.method != "POST":
        return redirect("ingest:upload_history")

    instance = (
        DatasetInstance.objects.select_related("dataset_type", "plant", "created_by__user")
        .filter(pk=pk)
        .first()
    )
    if not instance:
        raise Http404("Carga no encontrada.")

    user = request.user
    if not user.is_authenticated or not instance.created_by or instance.created_by.user_id != user.id:
        return redirect("ingest:upload_history")

    if instance.state == DatasetInstance.STATE_DRAFT:
        instance.state = DatasetInstance.STATE_SUBMITTED
        instance.last_error_summary = ""
        instance.save(update_fields=["state", "last_error_summary"])
        messages.success(request, "Dataset enviado a validación diaria.")
        record_action(
            "SUBMIT",
            request=request,
            module="Ingest",
            object_repr=f"{instance.dataset_type.name} | {instance.period}",
            details="Enviado a validación diaria",
        )

    return redirect("ingest:upload")


def edit_instance(request, pk):
    instance = (
        DatasetInstance.objects.select_related("dataset_type", "plant", "created_by__user")
        .filter(pk=pk)
        .first()
    )
    if not instance:
        raise Http404("Carga no encontrada.")

    user = request.user
    if not user.is_authenticated or not instance.created_by or instance.created_by.user_id != user.id:
        return redirect("ingest:upload_history")

    if instance.state != DatasetInstance.STATE_DRAFT:
        messages.info(request, "Solo se pueden editar datasets en estado borrador.")
        return redirect("ingest:upload_history")

    if request.method == "POST":
        form = DatasetInstanceEditForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.row_count = 0
            instance.error_count = 0
            instance.last_error_summary = ""
            instance.state = DatasetInstance.STATE_DRAFT
            instance.save()
            messages.success(request, "Dataset actualizado. Ahora puedes enviarlo a validación diaria.")
            record_action(
                "EDIT",
                request=request,
                module="Ingest",
                object_repr=f"{instance.dataset_type.name} | {instance.period}",
                details="Archivo corregido y reemplazado",
            )
            return redirect("ingest:upload")
    else:
        form = DatasetInstanceEditForm(instance=instance)

    return render(
        request,
        "ingest/instance_edit.html",
        {
            "instance": instance,
            "form": form,
        },
    )


def delete_instance(request, pk):
    if request.method != "POST":
        return redirect("ingest:upload_history")

    instance = DatasetInstance.objects.select_related("created_by__user").filter(pk=pk).first()
    if not instance:
        raise Http404("Carga no encontrada.")

    user = request.user
    if not user.is_authenticated or not instance.created_by or instance.created_by.user_id != user.id:
        return redirect("ingest:upload_history")

    if instance.state != DatasetInstance.STATE_DRAFT:
        messages.info(request, "Solo se pueden eliminar datasets en estado borrador.")
        return redirect("ingest:upload_history")

    record_action(
        "DELETE",
        request=request,
        module="Ingest",
        object_repr=f"{instance.dataset_type.name} | {instance.period}",
        details="Carga eliminada",
    )
    instance.delete()
    messages.success(request, "Dataset eliminado correctamente.")
    return redirect("ingest:upload")
