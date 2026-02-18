from __future__ import annotations

from django.contrib import messages
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.decorators import admin_role_required
from audit.utils import record_action

from .models import Category, Entity, Sector, Subsector


def _as_positive_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _redirect_manage_levels(open_sector_id: int | None = None):
    url = reverse("structure:manage_levels")
    if open_sector_id:
        return redirect(f"{url}?open={open_sector_id}")
    return redirect(url)


def _get_sector_operational_impact(sector: Sector) -> dict:
    from accounts.models import Membership
    from ingest.models import DatasetInstance, HistoricalImportBatch
    from projects.models import Project
    from schemas.models import DatasetType
    from validation.models import ValidationAction

    counts = {
        "memberships": Membership.objects.filter(entity__category__subsector__sector=sector).count(),
        "dataset_types": DatasetType.objects.filter(entity__category__subsector__sector=sector).count(),
        "approved_dataset_types": DatasetType.objects.filter(
            entity__category__subsector__sector=sector,
            status=DatasetType.STATUS_APPROVED,
        ).count(),
        "dataset_instances": DatasetInstance.objects.filter(entity__category__subsector__sector=sector).count(),
        "historical_imports": HistoricalImportBatch.objects.filter(entity__category__subsector__sector=sector).count(),
        "validation_actions": ValidationAction.objects.filter(
            dataset_instance__entity__category__subsector__sector=sector
        ).count(),
        "projects": Project.objects.filter(category__subsector__sector=sector).count(),
    }

    labels = {
        "memberships": "usuarios",
        "dataset_types": "esquemas",
        "approved_dataset_types": "esquemas aprobados",
        "dataset_instances": "cargas",
        "historical_imports": "cargas historicas",
        "validation_actions": "validaciones",
        "projects": "proyectos",
    }

    blocking_keys = (
        "memberships",
        "dataset_types",
        "dataset_instances",
        "historical_imports",
        "validation_actions",
        "projects",
    )
    has_blocking_data = any(counts[key] > 0 for key in blocking_keys)

    summary_items = []
    for key in blocking_keys:
        value = counts[key]
        if value > 0:
            summary_items.append(f"{labels[key]}: {value}")

    return {
        "counts": counts,
        "has_blocking_data": has_blocking_data,
        "summary": ", ".join(summary_items),
    }


def _get_entity_operational_impact(entity: Entity) -> dict:
    from accounts.models import Membership
    from ingest.models import DatasetInstance, HistoricalImportBatch
    from schemas.models import DatasetType
    from validation.models import ValidationAction

    counts = {
        "memberships": Membership.objects.filter(entity=entity).count(),
        "dataset_types": DatasetType.objects.filter(entity=entity).count(),
        "approved_dataset_types": DatasetType.objects.filter(
            entity=entity,
            status=DatasetType.STATUS_APPROVED,
        ).count(),
        "dataset_instances": DatasetInstance.objects.filter(entity=entity).count(),
        "historical_imports": HistoricalImportBatch.objects.filter(entity=entity).count(),
        "validation_actions": ValidationAction.objects.filter(dataset_instance__entity=entity).count(),
    }

    labels = {
        "memberships": "usuarios",
        "dataset_types": "esquemas",
        "approved_dataset_types": "esquemas aprobados",
        "dataset_instances": "cargas",
        "historical_imports": "cargas historicas",
        "validation_actions": "validaciones",
    }
    blocking_keys = (
        "memberships",
        "dataset_types",
        "dataset_instances",
        "historical_imports",
        "validation_actions",
    )
    has_blocking_data = any(counts[key] > 0 for key in blocking_keys)
    summary_items = [f"{labels[key]}: {counts[key]}" for key in blocking_keys if counts[key] > 0]

    return {
        "counts": counts,
        "has_blocking_data": has_blocking_data,
        "summary": ", ".join(summary_items),
    }


def _get_category_operational_impact(category: Category) -> dict:
    from projects.models import Project

    entity_ids = list(Entity.objects.filter(category=category).values_list("id", flat=True))
    projects_count = Project.objects.filter(category=category).count()

    operational = {
        "memberships": 0,
        "dataset_types": 0,
        "approved_dataset_types": 0,
        "dataset_instances": 0,
        "historical_imports": 0,
        "validation_actions": 0,
    }

    if entity_ids:
        from accounts.models import Membership
        from ingest.models import DatasetInstance, HistoricalImportBatch
        from schemas.models import DatasetType
        from validation.models import ValidationAction

        operational = {
            "memberships": Membership.objects.filter(entity_id__in=entity_ids).count(),
            "dataset_types": DatasetType.objects.filter(entity_id__in=entity_ids).count(),
            "approved_dataset_types": DatasetType.objects.filter(
                entity_id__in=entity_ids,
                status=DatasetType.STATUS_APPROVED,
            ).count(),
            "dataset_instances": DatasetInstance.objects.filter(entity_id__in=entity_ids).count(),
            "historical_imports": HistoricalImportBatch.objects.filter(entity_id__in=entity_ids).count(),
            "validation_actions": ValidationAction.objects.filter(
                dataset_instance__entity_id__in=entity_ids
            ).count(),
        }

    counts = {
        "projects": projects_count,
        **operational,
    }

    labels = {
        "projects": "proyectos",
        "memberships": "usuarios",
        "dataset_types": "esquemas",
        "approved_dataset_types": "esquemas aprobados",
        "dataset_instances": "cargas",
        "historical_imports": "cargas historicas",
        "validation_actions": "validaciones",
    }
    blocking_keys = (
        "projects",
        "memberships",
        "dataset_types",
        "dataset_instances",
        "historical_imports",
        "validation_actions",
    )
    has_blocking_data = any(counts[key] > 0 for key in blocking_keys)
    summary_items = [f"{labels[key]}: {counts[key]}" for key in blocking_keys if counts[key] > 0]

    return {
        "counts": counts,
        "has_blocking_data": has_blocking_data,
        "summary": ", ".join(summary_items),
    }


def _get_subsector_operational_impact(subsector: Subsector) -> dict:
    from projects.models import Project

    entity_ids = list(Entity.objects.filter(category__subsector=subsector).values_list("id", flat=True))
    projects_count = Project.objects.filter(category__subsector=subsector).count()

    operational = {
        "memberships": 0,
        "dataset_types": 0,
        "approved_dataset_types": 0,
        "dataset_instances": 0,
        "historical_imports": 0,
        "validation_actions": 0,
    }

    if entity_ids:
        from accounts.models import Membership
        from ingest.models import DatasetInstance, HistoricalImportBatch
        from schemas.models import DatasetType
        from validation.models import ValidationAction

        operational = {
            "memberships": Membership.objects.filter(entity_id__in=entity_ids).count(),
            "dataset_types": DatasetType.objects.filter(entity_id__in=entity_ids).count(),
            "approved_dataset_types": DatasetType.objects.filter(
                entity_id__in=entity_ids,
                status=DatasetType.STATUS_APPROVED,
            ).count(),
            "dataset_instances": DatasetInstance.objects.filter(entity_id__in=entity_ids).count(),
            "historical_imports": HistoricalImportBatch.objects.filter(entity_id__in=entity_ids).count(),
            "validation_actions": ValidationAction.objects.filter(
                dataset_instance__entity_id__in=entity_ids
            ).count(),
        }

    counts = {
        "projects": projects_count,
        **operational,
    }

    labels = {
        "projects": "proyectos",
        "memberships": "usuarios",
        "dataset_types": "esquemas",
        "approved_dataset_types": "esquemas aprobados",
        "dataset_instances": "cargas",
        "historical_imports": "cargas historicas",
        "validation_actions": "validaciones",
    }
    blocking_keys = (
        "projects",
        "memberships",
        "dataset_types",
        "dataset_instances",
        "historical_imports",
        "validation_actions",
    )
    has_blocking_data = any(counts[key] > 0 for key in blocking_keys)
    summary_items = [f"{labels[key]}: {counts[key]}" for key in blocking_keys if counts[key] > 0]

    return {
        "counts": counts,
        "has_blocking_data": has_blocking_data,
        "summary": ", ".join(summary_items),
    }


@admin_role_required
def manage_levels(request: HttpRequest) -> HttpResponse:
    action = request.POST.get("action") if request.method == "POST" else None

    if action == "create_sector":
        name = (request.POST.get("sector_name") or "").strip()
        description = (request.POST.get("sector_description") or "").strip()
        if not name:
            messages.error(request, "Debe ingresar el nombre del sector.")
            return _redirect_manage_levels()

        sector, created = Sector.objects.get_or_create(name=name, defaults={"description": description})
        if not created and description:
            sector.description = description
            sector.save(update_fields=["description", "updated_at"])

        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Sector:{sector.name}",
            details="Sector creado/actualizado",
        )
        messages.success(request, "Sector guardado.")
        return _redirect_manage_levels(open_sector_id=sector.id)

    if action == "create_subsector":
        sector_id = _as_positive_int(request.POST.get("sector_id"))
        open_sector_id = sector_id or _as_positive_int(request.POST.get("open_sector_id"))
        name = (request.POST.get("subsector_name") or "").strip()
        description = (request.POST.get("subsector_description") or "").strip()

        sector = Sector.objects.filter(id=sector_id).first() if sector_id else None
        if not sector:
            messages.error(request, "Debe seleccionar un sector valido.")
        elif not name:
            messages.error(request, "Debe definir el nombre del subsector.")
        else:
            subsector, created = Subsector.objects.get_or_create(
                sector=sector,
                name=name,
                defaults={"description": description},
            )
            if not created and description:
                subsector.description = description
                subsector.save(update_fields=["description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Subsector:{subsector}",
                details="Subsector creado/actualizado",
            )
            messages.success(request, "Subsector guardado.")
        return _redirect_manage_levels(open_sector_id=open_sector_id)

    if action == "create_category":
        subsector_id = _as_positive_int(request.POST.get("subsector_id"))
        open_sector_id = _as_positive_int(request.POST.get("open_sector_id"))
        name = (request.POST.get("category_name") or "").strip()
        description = (request.POST.get("category_description") or "").strip()

        subsector = Subsector.objects.select_related("sector").filter(id=subsector_id).first() if subsector_id else None
        if subsector and not open_sector_id:
            open_sector_id = subsector.sector_id

        if not subsector:
            messages.error(request, "Debe seleccionar un subsector valido.")
        elif not name:
            messages.error(request, "Debe definir el nombre de la categoria.")
        else:
            category, created = Category.objects.get_or_create(
                subsector=subsector,
                name=name,
                defaults={"description": description},
            )
            if not created and description:
                category.description = description
                category.save(update_fields=["description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Categoria:{category}",
                details="Categoria creada/actualizada",
            )
            messages.success(request, "Categoria guardada.")
        return _redirect_manage_levels(open_sector_id=open_sector_id)

    if action == "create_entity":
        category_id = _as_positive_int(request.POST.get("category_id"))
        open_sector_id = _as_positive_int(request.POST.get("open_sector_id"))
        code = (request.POST.get("entity_code") or "").strip()
        name = (request.POST.get("entity_name") or "").strip()
        description = (request.POST.get("entity_description") or "").strip()

        category = (
            Category.objects.select_related("subsector", "subsector__sector")
            .filter(id=category_id)
            .first()
            if category_id
            else None
        )

        if category and not open_sector_id:
            open_sector_id = category.subsector.sector_id

        if not category:
            messages.error(request, "Debe seleccionar una categoria valida.")
        elif not name:
            messages.error(request, "Debe definir el nombre de la entidad.")
        else:
            entity, created = Entity.objects.get_or_create(
                category=category,
                name=name,
                defaults={
                    "code": code,
                    "description": description,
                    "is_active": True,
                },
            )
            if not created:
                entity.code = code
                entity.description = description
                entity.is_active = True
                entity.save(update_fields=["code", "description", "is_active", "updated_at"])

            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Entidad:{entity.name}",
                details=f"Entidad creada/actualizada en categoria {category}",
            )
            messages.success(request, "Entidad guardada.")
        return _redirect_manage_levels(open_sector_id=open_sector_id)

    if action == "update_sector":
        sector_id = _as_positive_int(request.POST.get("sector_id"))
        open_sector_id = _as_positive_int(request.POST.get("open_sector_id")) or sector_id
        name = (request.POST.get("sector_name") or "").strip()
        description = (request.POST.get("sector_description") or "").strip()
        sector = Sector.objects.filter(id=sector_id).first() if sector_id else None

        if not sector or not name:
            messages.error(request, "Debe seleccionar un sector y definir el nombre.")
        elif Sector.objects.exclude(id=sector.id).filter(name=name).exists():
            messages.error(request, "Ya existe un sector con ese nombre.")
        else:
            sector.name = name
            sector.description = description
            sector.save(update_fields=["name", "description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Sector:{sector.name}",
                details="Sector actualizado",
            )
            messages.success(request, "Sector actualizado.")
        return _redirect_manage_levels(open_sector_id=open_sector_id)

    if action == "delete_sector":
        sector_id = _as_positive_int(request.POST.get("sector_id"))
        sector = Sector.objects.filter(id=sector_id).first() if sector_id else None
        if not sector:
            messages.error(request, "Sector no encontrado.")
            return _redirect_manage_levels()

        subsector_count = Subsector.objects.filter(sector=sector).count()
        impact = _get_sector_operational_impact(sector)

        if subsector_count > 0:
            messages.error(request, "No se puede eliminar: el sector tiene niveles asociados.")
            return _redirect_manage_levels(open_sector_id=sector.id)

        if impact["has_blocking_data"]:
            messages.error(
                request,
                f"No se puede eliminar: el sector tiene datos asociados ({impact['summary']}).",
            )
            return _redirect_manage_levels(open_sector_id=sector.id)

        sector_name = sector.name
        sector.delete()
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Sector:{sector_name}",
            details="Sector eliminado",
        )
        messages.success(request, "Sector eliminado.")
        return _redirect_manage_levels()

    if action == "update_subsector":
        subsector_id = _as_positive_int(request.POST.get("subsector_id"))
        open_sector_id = _as_positive_int(request.POST.get("open_sector_id"))
        name = (request.POST.get("subsector_name") or "").strip()
        description = (request.POST.get("subsector_description") or "").strip()
        subsector = Subsector.objects.select_related("sector").filter(id=subsector_id).first() if subsector_id else None

        if subsector and not open_sector_id:
            open_sector_id = subsector.sector_id

        if not subsector or not name:
            messages.error(request, "Debe seleccionar un subsector y definir el nombre.")
        elif Subsector.objects.exclude(id=subsector.id).filter(sector=subsector.sector, name=name).exists():
            messages.error(request, "Ya existe un subsector con ese nombre en el sector.")
        else:
            subsector.name = name
            subsector.description = description
            subsector.save(update_fields=["name", "description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Subsector:{subsector}",
                details="Subsector actualizado",
            )
            messages.success(request, "Subsector actualizado.")
        return _redirect_manage_levels(open_sector_id=open_sector_id)

    if action == "delete_subsector":
        subsector_id = _as_positive_int(request.POST.get("subsector_id"))
        subsector = Subsector.objects.select_related("sector").filter(id=subsector_id).first() if subsector_id else None
        if not subsector:
            messages.error(request, "Subsector no encontrado.")
            return _redirect_manage_levels()

        has_child_levels = Category.objects.filter(subsector=subsector).exists()
        impact = _get_subsector_operational_impact(subsector)

        if has_child_levels:
            messages.error(request, "No se puede eliminar: el subsector tiene niveles asociados.")
            return _redirect_manage_levels(open_sector_id=subsector.sector_id)

        if impact["has_blocking_data"]:
            messages.error(
                request,
                f"No se puede eliminar: el subsector tiene datos asociados ({impact['summary']}).",
            )
            return _redirect_manage_levels(open_sector_id=subsector.sector_id)

        sector_id = subsector.sector_id
        subsector_repr = str(subsector)
        subsector.delete()
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Subsector:{subsector_repr}",
            details="Subsector eliminado",
        )
        messages.success(request, "Subsector eliminado.")
        return _redirect_manage_levels(open_sector_id=sector_id)

    if action == "update_category":
        category_id = _as_positive_int(request.POST.get("category_id"))
        open_sector_id = _as_positive_int(request.POST.get("open_sector_id"))
        name = (request.POST.get("category_name") or "").strip()
        description = (request.POST.get("category_description") or "").strip()
        category = (
            Category.objects.select_related("subsector", "subsector__sector")
            .filter(id=category_id)
            .first()
            if category_id
            else None
        )

        if category and not open_sector_id:
            open_sector_id = category.subsector.sector_id

        if not category or not name:
            messages.error(request, "Debe seleccionar una categoria y definir el nombre.")
        elif Category.objects.exclude(id=category.id).filter(subsector=category.subsector, name=name).exists():
            messages.error(request, "Ya existe una categoria con ese nombre en el subsector.")
        else:
            category.name = name
            category.description = description
            category.save(update_fields=["name", "description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Categoria:{category}",
                details="Categoria actualizada",
            )
            messages.success(request, "Categoria actualizada.")
        return _redirect_manage_levels(open_sector_id=open_sector_id)

    if action == "delete_category":
        category_id = _as_positive_int(request.POST.get("category_id"))
        category = (
            Category.objects.select_related("subsector", "subsector__sector")
            .filter(id=category_id)
            .first()
            if category_id
            else None
        )
        if not category:
            messages.error(request, "Categoria no encontrada.")
            return _redirect_manage_levels()

        has_child_levels = Entity.objects.filter(category=category).exists()
        impact = _get_category_operational_impact(category)

        if has_child_levels:
            messages.error(request, "No se puede eliminar: la categoria tiene entidades asociadas.")
            return _redirect_manage_levels(open_sector_id=category.subsector.sector_id)

        if impact["has_blocking_data"]:
            messages.error(
                request,
                f"No se puede eliminar: la categoria tiene datos asociados ({impact['summary']}).",
            )
            return _redirect_manage_levels(open_sector_id=category.subsector.sector_id)

        sector_id = category.subsector.sector_id
        category_repr = str(category)
        category.delete()
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Categoria:{category_repr}",
            details="Categoria eliminada",
        )
        messages.success(request, "Categoria eliminada.")
        return _redirect_manage_levels(open_sector_id=sector_id)

    if action == "update_entity":
        entity_id = _as_positive_int(request.POST.get("entity_id"))
        open_sector_id = _as_positive_int(request.POST.get("open_sector_id"))
        category_id = _as_positive_int(request.POST.get("category_id"))
        code = (request.POST.get("entity_code") or "").strip()
        name = (request.POST.get("entity_name") or "").strip()
        description = (request.POST.get("entity_description") or "").strip()

        entity = (
            Entity.objects.select_related("category", "category__subsector", "category__subsector__sector")
            .filter(id=entity_id)
            .first()
            if entity_id
            else None
        )
        category = (
            Category.objects.select_related("subsector", "subsector__sector")
            .filter(id=category_id)
            .first()
            if category_id
            else None
        )

        if entity and not open_sector_id:
            open_sector_id = entity.category.subsector.sector_id

        if not entity or not category or not name:
            messages.error(request, "Debe completar nombre y categoria para la entidad.")
        elif Entity.objects.exclude(id=entity.id).filter(category=category, name=name).exists():
            messages.error(request, "Ya existe una entidad con ese nombre en la categoria.")
        else:
            entity.category = category
            entity.code = code
            entity.name = name
            entity.description = description
            entity.save(update_fields=["category", "code", "name", "description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Entidad:{entity.name}",
                details="Entidad actualizada",
            )
            messages.success(request, "Entidad actualizada.")
        return _redirect_manage_levels(open_sector_id=open_sector_id)

    if action == "delete_entity":
        entity_id = _as_positive_int(request.POST.get("entity_id"))
        entity = (
            Entity.objects.select_related("category", "category__subsector", "category__subsector__sector")
            .filter(id=entity_id)
            .first()
            if entity_id
            else None
        )
        if not entity:
            messages.error(request, "Entidad no encontrada.")
            return _redirect_manage_levels()

        impact = _get_entity_operational_impact(entity)
        if impact["has_blocking_data"]:
            messages.error(
                request,
                f"No se puede eliminar: la entidad tiene datos asociados ({impact['summary']}).",
            )
            return _redirect_manage_levels(open_sector_id=entity.category.subsector.sector_id)

        sector_id = entity.category.subsector.sector_id
        entity_name = entity.name
        entity.delete()
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Entidad:{entity_name}",
            details="Entidad eliminada",
        )
        messages.success(request, "Entidad eliminada.")
        return _redirect_manage_levels(open_sector_id=sector_id)

    if action == "toggle_sector":
        sector_id = _as_positive_int(request.POST.get("sector_id"))
        sector = Sector.objects.filter(id=sector_id).first() if sector_id else None
        if not sector:
            messages.error(request, "Sector no encontrado.")
            return _redirect_manage_levels()

        if sector.is_active:
            impact = _get_sector_operational_impact(sector)
            if impact["has_blocking_data"]:
                messages.error(
                    request,
                    f"No se puede desactivar: el sector tiene datos asociados ({impact['summary']}).",
                )
                return _redirect_manage_levels(open_sector_id=sector.id)

        sector.is_active = not sector.is_active
        sector.save(update_fields=["is_active", "updated_at"])
        status_text = "activado" if sector.is_active else "desactivado"
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Sector:{sector.name}",
            details=f"Sector {status_text}",
        )
        messages.success(request, f"Sector {status_text}.")
        return _redirect_manage_levels(open_sector_id=sector.id)

    if action == "toggle_subsector":
        subsector_id = _as_positive_int(request.POST.get("subsector_id"))
        subsector = Subsector.objects.select_related("sector").filter(id=subsector_id).first() if subsector_id else None
        if not subsector:
            messages.error(request, "Subsector no encontrado.")
            return _redirect_manage_levels()

        if subsector.is_active:
            has_child_levels = Category.objects.filter(subsector=subsector).exists()
            impact = _get_subsector_operational_impact(subsector)
            if has_child_levels or impact["has_blocking_data"]:
                reasons = []
                if has_child_levels:
                    reasons.append("tiene niveles asociados")
                if impact["has_blocking_data"]:
                    reasons.append(f"tiene datos asociados ({impact['summary']})")
                messages.error(request, f"No se puede desactivar: el subsector {' y '.join(reasons)}.")
                return _redirect_manage_levels(open_sector_id=subsector.sector_id)

        subsector.is_active = not subsector.is_active
        subsector.save(update_fields=["is_active", "updated_at"])
        status_text = "activado" if subsector.is_active else "desactivado"
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Subsector:{subsector}",
            details=f"Subsector {status_text}",
        )
        messages.success(request, f"Subsector {status_text}.")
        return _redirect_manage_levels(open_sector_id=subsector.sector_id)

    if action == "toggle_category":
        category_id = _as_positive_int(request.POST.get("category_id"))
        category = (
            Category.objects.select_related("subsector", "subsector__sector")
            .filter(id=category_id)
            .first()
            if category_id
            else None
        )
        if not category:
            messages.error(request, "Categoria no encontrada.")
            return _redirect_manage_levels()

        if category.is_active:
            has_child_levels = Entity.objects.filter(category=category).exists()
            impact = _get_category_operational_impact(category)
            if has_child_levels or impact["has_blocking_data"]:
                reasons = []
                if has_child_levels:
                    reasons.append("tiene entidades asociadas")
                if impact["has_blocking_data"]:
                    reasons.append(f"tiene datos asociados ({impact['summary']})")
                messages.error(request, f"No se puede desactivar: la categoria {' y '.join(reasons)}.")
                return _redirect_manage_levels(open_sector_id=category.subsector.sector_id)

        category.is_active = not category.is_active
        category.save(update_fields=["is_active", "updated_at"])
        status_text = "activada" if category.is_active else "desactivada"
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Categoria:{category}",
            details=f"Categoria {status_text}",
        )
        messages.success(request, f"Categoria {status_text}.")
        return _redirect_manage_levels(open_sector_id=category.subsector.sector_id)

    if action == "toggle_entity":
        entity_id = _as_positive_int(request.POST.get("entity_id"))
        entity = (
            Entity.objects.select_related("category", "category__subsector", "category__subsector__sector")
            .filter(id=entity_id)
            .first()
            if entity_id
            else None
        )
        if not entity:
            messages.error(request, "Entidad no encontrada.")
            return _redirect_manage_levels()

        if entity.is_active:
            impact = _get_entity_operational_impact(entity)
            if impact["has_blocking_data"]:
                messages.error(
                    request,
                    f"No se puede desactivar: la entidad tiene datos asociados ({impact['summary']}).",
                )
                return _redirect_manage_levels(open_sector_id=entity.category.subsector.sector_id)

        entity.is_active = not entity.is_active
        entity.save(update_fields=["is_active", "updated_at"])
        status_text = "activada" if entity.is_active else "desactivada"
        record_action(
            "OTHER",
            request=request,
            module="structure",
            object_repr=f"Entidad:{entity.name}",
            details=f"Entidad {status_text}",
        )
        messages.success(request, f"Entidad {status_text}.")
        return _redirect_manage_levels(open_sector_id=entity.category.subsector.sector_id)

    sectors = (
        Sector.objects.prefetch_related(
            Prefetch(
                "subsectors",
                queryset=Subsector.objects.prefetch_related(
                    Prefetch(
                        "categories",
                        queryset=Category.objects.prefetch_related(
                            Prefetch("entities", queryset=Entity.objects.order_by("name"))
                        ).order_by("name"),
                    )
                ).order_by("name"),
            )
        )
        .order_by("name")
    )

    sector_cards = []
    sector_payload = {}

    for sector in sectors:
        subsector_items = list(sector.subsectors.all())
        category_count = 0
        entity_count = 0
        category_labels = []
        entity_labels = []

        payload_subsectors = []
        payload_categories = []

        subsector_rows = []
        category_rows = []
        entity_rows = []

        for subsector in subsector_items:
            payload_subsectors.append(
                {
                    "id": subsector.id,
                    "name": subsector.name,
                    "is_active": subsector.is_active,
                }
            )

            category_items = list(subsector.categories.all())
            has_child_levels_subsector = len(category_items) > 0
            subsector_impact = _get_subsector_operational_impact(subsector)
            subsector_can_delete = not has_child_levels_subsector and not subsector_impact["has_blocking_data"]
            subsector_can_deactivate = not has_child_levels_subsector and not subsector_impact["has_blocking_data"]

            if has_child_levels_subsector:
                subsector_delete_reason = "Tiene categorias o entidades asociadas."
                subsector_deactivate_reason = "Tiene categorias o entidades asociadas."
            elif subsector_impact["has_blocking_data"]:
                subsector_delete_reason = f"Tiene datos asociados ({subsector_impact['summary']})."
                subsector_deactivate_reason = f"Tiene datos asociados ({subsector_impact['summary']})."
            else:
                subsector_delete_reason = ""
                subsector_deactivate_reason = ""

            subsector_rows.append(
                {
                    "id": subsector.id,
                    "name": subsector.name,
                    "description": subsector.description,
                    "is_active": subsector.is_active,
                    "can_delete": subsector_can_delete,
                    "can_deactivate": subsector_can_deactivate,
                    "impact_summary": subsector_impact["summary"],
                    "delete_block_reason": subsector_delete_reason,
                    "deactivate_block_reason": subsector_deactivate_reason,
                }
            )

            for category in category_items:
                category_count += 1
                category_labels.append(f"{subsector.name} / {category.name}")
                payload_categories.append(
                    {
                        "id": category.id,
                        "name": category.name,
                        "is_active": category.is_active,
                        "subsector_id": subsector.id,
                        "subsector_name": subsector.name,
                    }
                )

                entity_items = list(category.entities.all())
                has_child_levels_category = len(entity_items) > 0
                category_impact = _get_category_operational_impact(category)
                category_can_delete = not has_child_levels_category and not category_impact["has_blocking_data"]
                category_can_deactivate = not has_child_levels_category and not category_impact["has_blocking_data"]

                if has_child_levels_category:
                    category_delete_reason = "Tiene entidades asociadas."
                    category_deactivate_reason = "Tiene entidades asociadas."
                elif category_impact["has_blocking_data"]:
                    category_delete_reason = f"Tiene datos asociados ({category_impact['summary']})."
                    category_deactivate_reason = f"Tiene datos asociados ({category_impact['summary']})."
                else:
                    category_delete_reason = ""
                    category_deactivate_reason = ""

                category_rows.append(
                    {
                        "id": category.id,
                        "name": category.name,
                        "description": category.description,
                        "is_active": category.is_active,
                        "subsector_id": subsector.id,
                        "subsector_name": subsector.name,
                        "can_delete": category_can_delete,
                        "can_deactivate": category_can_deactivate,
                        "impact_summary": category_impact["summary"],
                        "delete_block_reason": category_delete_reason,
                        "deactivate_block_reason": category_deactivate_reason,
                    }
                )

                for entity in entity_items:
                    entity_count += 1
                    entity_labels.append(entity.name)

                    entity_impact = _get_entity_operational_impact(entity)
                    entity_can_delete = not entity_impact["has_blocking_data"]
                    entity_can_deactivate = not entity_impact["has_blocking_data"]
                    entity_delete_reason = (
                        f"Tiene datos asociados ({entity_impact['summary']})."
                        if entity_impact["has_blocking_data"]
                        else ""
                    )
                    entity_deactivate_reason = entity_delete_reason

                    entity_rows.append(
                        {
                            "id": entity.id,
                            "name": entity.name,
                            "code": entity.code,
                            "description": entity.description,
                            "is_active": entity.is_active,
                            "category_id": category.id,
                            "category_name": category.name,
                            "subsector_name": subsector.name,
                            "can_delete": entity_can_delete,
                            "can_deactivate": entity_can_deactivate,
                            "impact_summary": entity_impact["summary"],
                            "delete_block_reason": entity_delete_reason,
                            "deactivate_block_reason": entity_deactivate_reason,
                        }
                    )

        impact = _get_sector_operational_impact(sector)
        has_child_levels = len(subsector_items) > 0
        can_delete = not has_child_levels and not impact["has_blocking_data"]
        can_deactivate = not impact["has_blocking_data"]

        if has_child_levels:
            delete_block_reason = "Tiene niveles asociados (subsectores/categorias/entidades)."
        elif impact["has_blocking_data"]:
            delete_block_reason = f"Tiene datos asociados ({impact['summary']})."
        else:
            delete_block_reason = ""

        deactivate_block_reason = (
            f"Tiene datos asociados ({impact['summary']})."
            if impact["has_blocking_data"]
            else ""
        )

        sector_cards.append(
            {
                "sector": sector,
                "subsectors": subsector_items,
                "subsector_count": len(subsector_items),
                "category_count": category_count,
                "entity_count": entity_count,
                "subsector_names": [item.name for item in subsector_items[:6]],
                "category_names": category_labels[:6],
                "entity_names": entity_labels[:6],
                "has_more_subsectors": len(subsector_items) > 6,
                "has_more_categories": category_count > 6,
                "has_more_entities": entity_count > 6,
                "can_delete": can_delete,
                "can_deactivate": can_deactivate,
                "impact_summary": impact["summary"],
                "delete_block_reason": delete_block_reason,
                "deactivate_block_reason": deactivate_block_reason,
                "subsector_rows": subsector_rows,
                "category_rows": category_rows,
                "entity_rows": entity_rows,
            }
        )

        sector_payload[str(sector.id)] = {
            "subsectors": payload_subsectors,
            "categories": payload_categories,
        }

    context = {
        "sector_cards": sector_cards,
        "open_sector_id": _as_positive_int(request.GET.get("open")),
        "sector_payload": sector_payload,
    }
    return render(request, "structure/manage_levels.html", context)

