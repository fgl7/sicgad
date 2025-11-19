from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import Membership
from ingest.models import DatasetInstance
from schemas.models import DatasetType

from .forms import ValidationDecisionForm
from .models import ValidationAction


@login_required
def inbox(request):
    """
    Bandeja de validacion:
    - Usa can_validate_daily / can_validate_monthly para decidir que datasets ve cada validador.
    """
    daily_memberships = Membership.objects.filter(
        user=request.user,
        role="VALIDATOR",
        is_active=True,
        can_validate_daily=True,
    )
    monthly_memberships = Membership.objects.filter(
        user=request.user,
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

    return render(request, "validate/inbox.html", {"items": items})


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
                messages.success(request, "Dataset aprobado correctamente.")
            else:
                instance.state = DatasetInstance.STATE_DRAFT
                instance.save()
                messages.warning(request, "Dataset rechazado y devuelto a borrador.")

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
