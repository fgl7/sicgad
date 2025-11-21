from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.models import Membership
from audit.models import AuditLog
from ingest.models import DatasetInstance
from schemas.models import DatasetType


def landing(request):
    return render(request, "landing.html")


@login_required
def home(request):
    user = request.user
    is_admin = False
    if user.is_authenticated:
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()

    # Estado rápido: algunos contadores básicos
    total_schemas = DatasetType.objects.count()
    total_instances = DatasetInstance.objects.count()
    pending_instances = DatasetInstance.objects.filter(
        state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1]
    ).count()
    published_instances = DatasetInstance.objects.filter(state=DatasetInstance.STATE_PUBLISHED).count()

    # Últimas acciones de auditoría (visibles para todos por transparencia)
    recent_logs = AuditLog.objects.select_related("user").order_by("-created_at")[:10]

    # Últimas cargas de datos (independiente del estado)
    recent_instances = (
        DatasetInstance.objects.select_related("dataset_type", "plant")
        .order_by("-created_at")[:5]
    )

    return render(
        request,
        "kpis/home.html",
        {
            "is_admin": is_admin,
            "total_schemas": total_schemas,
            "total_instances": total_instances,
            "pending_instances": pending_instances,
            "published_instances": published_instances,
            "recent_logs": recent_logs,
            "recent_instances": recent_instances,
        },
    )
