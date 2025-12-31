from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict

from django.db.models import Q

from accounts.models import Membership
from ingest.models import DatasetInstance
from schemas.models import DatasetType
from schemas.services import previous_month_range
from .models import ValidationAction

UNKNOWN_INSTITUTION = "UNKNOWN"


def _collect_monthly_requirements(instance: DatasetInstance) -> Dict[str, int]:
    """
    Obtiene el nivel máximo requerido por institución para el dataset mensual indicado.
    """
    freq = instance.dataset_type.validation_frequency
    if freq == DatasetType.WEEKLY:
        freq_filter = Q(can_validate_weekly=True)
    elif freq == DatasetType.FLEXIBLE:
        freq_filter = Q(can_validate_projections=True)
    else:
        freq_filter = Q(can_validate_monthly=True)

    validators = (
        Membership.objects.filter(
            role="VALIDATOR",
            is_active=True,
        )
        .filter(freq_filter)
        .filter(Q(plant=instance.plant) | Q(plant__isnull=True))
    )

    requirements: Dict[str, int] = {}
    for membership in validators:
        institution = (
            membership.institution.code
            if membership.institution
            else UNKNOWN_INSTITUTION
        )
        level = membership.validation_level or 1
        current = requirements.get(institution, 0)
        if level > current:
            requirements[institution] = level
    return requirements


def determine_monthly_state(instance: DatasetInstance) -> str:
    """
    Calcula el estado agregado para un dataset mensual considerando todas las instituciones.
    """
    requirements = _collect_monthly_requirements(instance)
    if not requirements:
        return DatasetInstance.STATE_PUBLISHED

    approvals = instance.validation_actions.filter(
        decision=ValidationAction.DECISION_APPROVE
    ).select_related("validator")
    progress: Dict[str, int] = defaultdict(int)
    for action in approvals:
        if action.validator:
            institution = (
                action.validator.institution.code
                if action.validator.institution
                else UNKNOWN_INSTITUTION
            )
        else:
            institution = UNKNOWN_INSTITUTION
        level = action.level or 1
        if level > progress[institution]:
            progress[institution] = level

    all_completed = all(
        progress.get(institution, 0) >= required_level
        for institution, required_level in requirements.items()
    )
    if all_completed:
        return DatasetInstance.STATE_PUBLISHED
    if approvals.exists():
        return DatasetInstance.STATE_VALIDATED_L1
    return DatasetInstance.STATE_SUBMITTED


def determine_periodic_state(instance: DatasetInstance) -> str:
    """
    Datasets semanales y mensuales usan la misma lІgica multi-instituciІn.
    """
    return determine_monthly_state(instance)


def ensure_monthly_state(instance: DatasetInstance, *, save: bool = True) -> str:
    """
    Recalcula el estado mensual y lo guarda si es necesario.
    """
    desired_state = determine_periodic_state(instance)
    if save and desired_state != instance.state:
        instance.state = desired_state
        instance.save(update_fields=["state"])
    return desired_state


def sync_previous_month_certifications(reference_date: date | None = None) -> None:
    """
    Fuerza la sincronización del estado para las certificaciones del mes anterior.
    Se ejecuta de forma lazy al iniciar sesión para mantener consistencia.
    """
    _, prev_month_end = previous_month_range(reference_date)
    monthly_instances = DatasetInstance.objects.filter(
        dataset_type__validation_frequency=DatasetType.MONTHLY,
        dataset_type__is_certification=True,
        period=prev_month_end,
    )
    for instance in monthly_instances:
        ensure_monthly_state(instance, save=True)
