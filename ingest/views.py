from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.models import Membership
from schemas.models import DatasetType

from .forms import DatasetInstanceUploadForm
from .models import DatasetInstance


def upload(request):
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
            instance.row_count = 0  # Aquí luego se llenará con el resultado real de la validación
            instance.error_count = 0
            instance.last_error_summary = ""
            instance.save()

            messages.success(request, "Archivo subido correctamente (validación pendiente de implementar).")
            return redirect(reverse("ingest:upload_history"))
    else:
        form = DatasetInstanceUploadForm()

    return render(request, "ingest/upload.html", {"form": form})


def upload_history(request):
    if request.user.is_authenticated:
        instances = DatasetInstance.objects.select_related("dataset_type", "plant").order_by("-created_at")[:50]
    else:
        instances = DatasetInstance.objects.none()

    return render(request, "ingest/upload_history.html", {"instances": instances})

