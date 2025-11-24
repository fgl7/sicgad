from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import Membership
from ingest.models import DatasetInstance
from ingest.utils import materialize_instance
from schemas.models import DatasetType

from audit.utils import record_action
from .forms import ValidationDecisionForm
from .models import ValidationAction


@login_required
def inbox(request):
    """
    Bandeja de validacion para validadores.
    Los administradores usarán una vista de resumen separada.
    """
    user = request.user

    if user.is_superuser or Membership.objects.filter(
        user=user, role="ADMIN", is_active=True
    ).exists():
        return redirect("validation:admin_overview")

    # Si el usuario no es validador, lo redirigimos al historial de cargas,
    # donde podrá ver el estado y comentarios de sus datasets.
    is_validator = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
    ).exists()
    if not is_validator:
        messages.info(
            request,
            "La bandeja de validación está disponible solo para validadores. "
            "Puedes revisar el estado y comentarios de tus cargas en el historial.",
        )
        return redirect("ingest:upload_history")

    daily_memberships = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_daily=True,
    )
    monthly_memberships = Membership.objects.filter(
        user=user,
        role="VALIDATOR",
        is_active=True,
        can_validate_monthly=True,
    )

    daily_plants = [m.plant_id for m in daily_memberships if m.plant_id]
    monthly_plants = [m.plant_id for m in monthly_memberships if m.plant_id]

    has_global_daily = any(m.plant_id is None for m in daily_memberships)
    has_global_monthly = any(m.plant_id is None for m in monthly_memberships)

    base_qs = DatasetInstance.objects.select_related("dataset_type", "plant").filter(
        state__in=[DatasetInstance.STATE_SUBMITTED, DatasetInstance.STATE_VALIDATED_L1]
    )

    daily_filter = Q(
        dataset_type__validation_frequency=DatasetType.DAILY,
        plant_id__in=daily_plants,
    )
    if has_global_daily:
        daily_filter |= Q(dataset_type__validation_frequency=DatasetType.DAILY)

    monthly_filter = Q(
        dataset_type__validation_frequency=DatasetType.MONTHLY,
        plant_id__in=monthly_plants,
    )
    if has_global_monthly:
        monthly_filter |= Q(dataset_type__validation_frequency=DatasetType.MONTHLY)

    items = base_qs.filter(daily_filter | monthly_filter).order_by("-created_at")

    # Historial de validaciones realizadas por este usuario (como validador)
    history_actions = (
        ValidationAction.objects.select_related(
            "dataset_instance",
            "dataset_instance__dataset_type",
            "dataset_instance__plant",
        )
        .filter(validator__user=user, validator__is_active=True)
        .order_by("-created_at")[:50]
    )

    return render(
        request,
        "validate/inbox.html",
        {
            "items": items,
            "history_actions": history_actions,
        },
    )


@login_required
def admin_overview(request):
    """
    Historial y estado de validaciones para Administracion,
    separado en datasets diarios y mensuales.
    """
    if not (
        request.user.is_superuser
        or Membership.objects.filter(user=request.user, role="ADMIN", is_active=True).exists()
    ):
        return redirect("validation:inbox")

    daily_instances = (
        DatasetInstance.objects.select_related("dataset_type", "plant")
        .filter(dataset_type__validation_frequency=DatasetType.DAILY)
        .order_by("-created_at")[:100]
    )
    monthly_instances = (
        DatasetInstance.objects.select_related("dataset_type", "plant")
        .filter(dataset_type__validation_frequency=DatasetType.MONTHLY)
        .order_by("-created_at")[:100]
    )

    return render(
        request,
        "validate/admin_overview.html",
        {
            "daily_instances": daily_instances,
            "monthly_instances": monthly_instances,
        },
    )


@login_required
def detail(request, pk):
    instance = get_object_or_404(
        DatasetInstance.objects.select_related("dataset_type", "plant"),
        pk=pk,
    )

    freq = instance.dataset_type.validation_frequency

    base_qs = Membership.objects.filter(user=request.user, role="VALIDATOR", is_active=True)
    if freq == DatasetType.DAILY:
        base_qs = base_qs.filter(can_validate_daily=True)
    else:
        base_qs = base_qs.filter(can_validate_monthly=True)

    # Primero intentamos un membership especifico de planta; si no hay, usamos uno global
    membership = base_qs.filter(plant=instance.plant).order_by("validation_level").first()
    if not membership:
        membership = base_qs.filter(plant__isnull=True).order_by("validation_level").first()

    if not membership:
        messages.error(request, "No tiene permisos de validacion sobre este dataset.")
        return redirect(reverse("validation:inbox"))

    if request.method == "POST":
        form = ValidationDecisionForm(request.POST)
        if form.is_valid():
            action: ValidationAction = form.save(commit=False)
            action.dataset_instance = instance
            action.validator = membership
            action.user = request.user
            action.level = membership.validation_level if membership.validation_level else 1
            action.save()

            if action.decision == ValidationAction.DECISION_APPROVE:
                freq = instance.dataset_type.validation_frequency

                if freq == DatasetType.DAILY:
                    # Flujo diario: un solo nivel (Jefe de planta)
                    instance.state = DatasetInstance.STATE_PUBLISHED
                else:
                    # Flujo mensual / general: varios niveles de validacion
                    validators = Membership.objects.filter(
                        role="VALIDATOR",
                        is_active=True,
                        can_validate_monthly=True,
                    ).filter(Q(plant=instance.plant) | Q(plant__isnull=True))
                    if validators.exists():
                        max_level = max(v.validation_level or 1 for v in validators)
                    else:
                        max_level = action.level

                    previous_actions = instance.validation_actions.filter(
                        decision=ValidationAction.DECISION_APPROVE
                    )
                    if previous_actions.exists():
                        current_level = max(a.level for a in previous_actions)
                    else:
                        current_level = 0

                    if action.level <= current_level:
                        pass
                    else:
                        if action.level < max_level:
                            instance.state = DatasetInstance.STATE_VALIDATED_L1
                        else:
                            instance.state = DatasetInstance.STATE_PUBLISHED

                instance.save()

                if instance.state == DatasetInstance.STATE_PUBLISHED:
                    materialize_instance(instance)
                messages.success(request, "Dataset aprobado correctamente.")
                record_action(
                    "VALIDATION",
                    request=request,
                    module="Validation",
                    object_repr=f"{instance.dataset_type.name} | {instance.period}",
                    details="Aprobado",
                )
            else:
                instance.state = DatasetInstance.STATE_DRAFT
                instance.last_error_summary = action.comment or ""
                instance.save(update_fields=["state", "last_error_summary"])
                messages.warning(request, "Dataset rechazado y devuelto a borrador.")
                record_action(
                    "VALIDATION",
                    request=request,
                    module="Validation",
                    object_repr=f"{instance.dataset_type.name} | {instance.period}",
                    details="Rechazado",
                )

            return redirect(reverse("validation:inbox"))
    else:
        form = ValidationDecisionForm()

    actions = instance.validation_actions.select_related("user").all()

    return render(
        request,
        "validate/detail.html",
        {
            "instance": instance,
            "form": form,
            "actions": actions,
        },
    )
