from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from audit.utils import record_action
from accounts.decorators import admin_role_required

from .models import Category, Entity, EntityType, Sector, Subsector

SESSION_SECTOR_KEY = "structure_current_sector_id"
SESSION_SUBSECTOR_KEY = "structure_current_subsector_id"
SESSION_CATEGORY_KEY = "structure_current_category_id"


def _set_current_ids(request, sector_id=None, subsector_id=None, category_id=None):
    if sector_id is not None:
        request.session[SESSION_SECTOR_KEY] = sector_id
    if subsector_id is not None:
        request.session[SESSION_SUBSECTOR_KEY] = subsector_id
    if category_id is not None:
        request.session[SESSION_CATEGORY_KEY] = category_id


def _clear_current_ids(request, clear_sector=False, clear_subsector=False, clear_category=False):
    if clear_sector:
        request.session.pop(SESSION_SECTOR_KEY, None)
    if clear_subsector:
        request.session.pop(SESSION_SUBSECTOR_KEY, None)
    if clear_category:
        request.session.pop(SESSION_CATEGORY_KEY, None)


def _resolve_current_tree(request):
    current_sector = None
    current_subsector = None
    current_category = None

    sector_id = request.session.get(SESSION_SECTOR_KEY)
    if sector_id:
        current_sector = Sector.objects.filter(id=sector_id, is_active=True).first()

    if not current_sector:
        current_sector = Sector.objects.filter(is_active=True).order_by("-created_at").first()
        if current_sector:
            _set_current_ids(request, sector_id=current_sector.id)
        else:
            _clear_current_ids(request, clear_sector=True, clear_subsector=True, clear_category=True)

    subsector_id = request.session.get(SESSION_SUBSECTOR_KEY)
    if current_sector and subsector_id:
        current_subsector = Subsector.objects.filter(
            id=subsector_id, is_active=True, sector=current_sector
        ).first()

    if current_sector and not current_subsector:
        current_subsector = (
            Subsector.objects.filter(is_active=True, sector=current_sector)
            .order_by("-created_at")
            .first()
        )
        if current_subsector:
            _set_current_ids(request, subsector_id=current_subsector.id)
        else:
            _clear_current_ids(request, clear_subsector=True, clear_category=True)
    elif not current_sector:
        _clear_current_ids(request, clear_subsector=True, clear_category=True)

    category_id = request.session.get(SESSION_CATEGORY_KEY)
    if current_subsector and category_id:
        current_category = Category.objects.filter(
            id=category_id, is_active=True, subsector=current_subsector
        ).first()

    if current_subsector and not current_category:
        current_category = (
            Category.objects.filter(is_active=True, subsector=current_subsector)
            .order_by("-created_at")
            .first()
        )
        if current_category:
            _set_current_ids(request, category_id=current_category.id)
        else:
            _clear_current_ids(request, clear_category=True)
    elif not current_subsector:
        _clear_current_ids(request, clear_category=True)

    return current_sector, current_subsector, current_category


@admin_role_required
def manage_levels(request: HttpRequest) -> HttpResponse:
    action = request.POST.get("action") if request.method == "POST" else None
    current_sector, current_subsector, current_category = _resolve_current_tree(request)

    if action == "create_sector":
        name = (request.POST.get("sector_name") or "").strip()
        description = (request.POST.get("sector_description") or "").strip()
        if not name:
            messages.error(request, "Debe ingresar el nombre del sector.")
        else:
            sector, created = Sector.objects.get_or_create(
                name=name, defaults={"description": description}
            )
            if not created and description:
                sector.description = description
                sector.save(update_fields=["description", "updated_at"])
            _set_current_ids(request, sector_id=sector.id)
            _clear_current_ids(request, clear_subsector=True, clear_category=True)
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Sector:{sector.name}",
                details="Sector creado/actualizado",
            )
            messages.success(request, "Sector guardado.")
        return redirect("structure:manage_levels")

    if action == "set_current_sector":
        sector_id = request.POST.get("sector_id")
        sector = Sector.objects.filter(id=sector_id, is_active=True).first() if sector_id else None
        if not sector:
            messages.error(request, "Sector no valido.")
        else:
            _set_current_ids(request, sector_id=sector.id)
            _clear_current_ids(request, clear_subsector=True, clear_category=True)
            messages.info(request, f"Sector activo: {sector.name}")
        return redirect("structure:manage_levels")

    if action == "create_subsector":
        name = (request.POST.get("subsector_name") or "").strip()
        description = (request.POST.get("subsector_description") or "").strip()
        if not current_sector:
            messages.error(request, "Primero debe crear un sector.")
        elif not name:
            messages.error(request, "Debe definir el nombre del subsector.")
        else:
            subsector, created = Subsector.objects.get_or_create(
                sector=current_sector, name=name, defaults={"description": description}
            )
            if not created and description:
                subsector.description = description
                subsector.save(update_fields=["description", "updated_at"])
            _set_current_ids(request, subsector_id=subsector.id)
            _clear_current_ids(request, clear_category=True)
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Subsector:{subsector}",
                details="Subsector creado/actualizado",
            )
            messages.success(request, "Subsector guardado.")
        return redirect("structure:manage_levels")

    if action == "set_current_subsector":
        subsector_id = request.POST.get("subsector_id")
        if not current_sector:
            messages.error(request, "Primero seleccione un sector.")
        else:
            subsector = Subsector.objects.filter(
                id=subsector_id,
                is_active=True,
                sector=current_sector,
            ).first() if subsector_id else None
            if not subsector:
                messages.error(request, "Subsector no valido para el sector actual.")
            else:
                _set_current_ids(request, subsector_id=subsector.id)
                _clear_current_ids(request, clear_category=True)
                messages.info(request, f"Subsector activo: {subsector.name}")
        return redirect("structure:manage_levels")

    if action == "create_category":
        name = (request.POST.get("category_name") or "").strip()
        description = (request.POST.get("category_description") or "").strip()
        if not current_subsector:
            messages.error(request, "Primero debe crear un subsector.")
        elif not name:
            messages.error(request, "Debe definir el nombre de la categoria.")
        else:
            category, created = Category.objects.get_or_create(
                subsector=current_subsector, name=name, defaults={"description": description}
            )
            if not created and description:
                category.description = description
                category.save(update_fields=["description", "updated_at"])
            _set_current_ids(request, category_id=category.id)
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Categoria:{category}",
                details="Categoria creada/actualizada",
            )
            messages.success(request, "Categoria guardada.")
        return redirect("structure:manage_levels")

    if action == "update_sector":
        sector_id = request.POST.get("sector_id")
        name = (request.POST.get("sector_name") or "").strip()
        description = (request.POST.get("sector_description") or "").strip()
        sector = Sector.objects.filter(id=sector_id).first() if sector_id else None
        if not sector or not name:
            messages.error(request, "Debe seleccionar un sector y definir el nombre.")
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
        return redirect("structure:manage_levels")

    if action == "deactivate_sector":
        sector_id = request.POST.get("sector_id")
        sector = Sector.objects.filter(id=sector_id).first() if sector_id else None
        if not sector:
            messages.error(request, "Sector no encontrado.")
        else:
            sector.is_active = False
            sector.save(update_fields=["is_active", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Sector:{sector.name}",
                details="Sector desactivado",
            )
            messages.success(request, "Sector desactivado.")
        return redirect("structure:manage_levels")

    if action == "update_subsector":
        subsector_id = request.POST.get("subsector_id")
        name = (request.POST.get("subsector_name") or "").strip()
        description = (request.POST.get("subsector_description") or "").strip()
        subsector = Subsector.objects.filter(id=subsector_id).first() if subsector_id else None
        if not subsector or not name:
            messages.error(request, "Debe seleccionar un subsector y definir el nombre.")
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
        return redirect("structure:manage_levels")

    if action == "deactivate_subsector":
        subsector_id = request.POST.get("subsector_id")
        subsector = Subsector.objects.filter(id=subsector_id).first() if subsector_id else None
        if not subsector:
            messages.error(request, "Subsector no encontrado.")
        else:
            subsector.is_active = False
            subsector.save(update_fields=["is_active", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Subsector:{subsector}",
                details="Subsector desactivado",
            )
            messages.success(request, "Subsector desactivado.")
        return redirect("structure:manage_levels")

    if action == "update_category":
        category_id = request.POST.get("category_id")
        name = (request.POST.get("category_name") or "").strip()
        description = (request.POST.get("category_description") or "").strip()
        category = Category.objects.filter(id=category_id).first() if category_id else None
        if not category or not name:
            messages.error(request, "Debe seleccionar una categoria y definir el nombre.")
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
        return redirect("structure:manage_levels")

    if action == "deactivate_category":
        category_id = request.POST.get("category_id")
        category = Category.objects.filter(id=category_id).first() if category_id else None
        if not category:
            messages.error(request, "Categoria no encontrada.")
        else:
            category.is_active = False
            category.save(update_fields=["is_active", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Categoria:{category}",
                details="Categoria desactivada",
            )
            messages.success(request, "Categoria desactivada.")
        return redirect("structure:manage_levels")

    if action == "set_current_category":
        category_id = request.POST.get("category_id")
        if not current_subsector:
            messages.error(request, "Primero seleccione un subsector.")
        else:
            category = Category.objects.filter(
                id=category_id,
                is_active=True,
                subsector=current_subsector,
            ).first() if category_id else None
            if not category:
                messages.error(request, "Categoria no valida para el subsector actual.")
            else:
                _set_current_ids(request, category_id=category.id)
                messages.info(request, f"Categoria activa: {category.name}")
        return redirect("structure:manage_levels")

    if action == "create_entity_type":
        name = (request.POST.get("entity_type_name") or "").strip()
        description = (request.POST.get("entity_type_description") or "").strip()
        if not name:
            messages.error(request, "Debe definir el nombre del tipo de entidad.")
        else:
            entity_type, created = EntityType.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            if not created:
                entity_type.description = description
                entity_type.save(update_fields=["description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"TipoEntidad:{entity_type.name}",
                details="Tipo de entidad creado/actualizado",
            )
            messages.success(request, "Tipo de entidad guardado.")
        return redirect("structure:manage_levels")

    if action == "create_entity":
        entity_type_id = request.POST.get("entity_type_id")
        code = (request.POST.get("entity_code") or "").strip()
        name = (request.POST.get("entity_name") or "").strip()
        description = (request.POST.get("entity_description") or "").strip()
        entity_type = EntityType.objects.filter(id=entity_type_id, is_active=True).first() if entity_type_id else None
        if not current_category:
            messages.error(request, "Primero debe crear una categoria.")
        elif not entity_type:
            messages.error(request, "Debe seleccionar un tipo de entidad.")
        elif not name:
            messages.error(request, "Debe definir el nombre de la entidad.")
        else:
            entity = Entity.objects.create(
                category=current_category,
                entity_type=entity_type,
                code=code,
                name=name,
                description=description,
                is_active=True,
            )
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Entidad:{entity.entity_type.name}:{entity.name}",
                details=f"Entidad creada en categoria {current_category}",
            )
            messages.success(request, "Entidad creada.")
        return redirect("structure:manage_levels")

    if action == "update_entity_type":
        entity_type_id = request.POST.get("entity_type_id")
        name = (request.POST.get("entity_type_name") or "").strip()
        description = (request.POST.get("entity_type_description") or "").strip()
        entity_type = EntityType.objects.filter(id=entity_type_id).first() if entity_type_id else None
        if not entity_type or not name:
            messages.error(request, "Debe seleccionar y nombrar el tipo de entidad.")
        else:
            entity_type.name = name
            entity_type.description = description
            entity_type.save(update_fields=["name", "description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"TipoEntidad:{entity_type.name}",
                details="Tipo de entidad actualizado",
            )
            messages.success(request, "Tipo de entidad actualizado.")
        return redirect("structure:manage_levels")

    if action == "deactivate_entity_type":
        entity_type_id = request.POST.get("entity_type_id")
        entity_type = EntityType.objects.filter(id=entity_type_id).first() if entity_type_id else None
        if not entity_type:
            messages.error(request, "Tipo de entidad no encontrado.")
        else:
            entity_type.is_active = False
            entity_type.save(update_fields=["is_active", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"TipoEntidad:{entity_type.name}",
                details="Tipo de entidad desactivado",
            )
            messages.success(request, "Tipo de entidad desactivado.")
        return redirect("structure:manage_levels")

    if action == "update_entity":
        entity_id = request.POST.get("entity_id")
        entity_type_id = request.POST.get("entity_type_id")
        category_id = request.POST.get("category_id")
        code = (request.POST.get("entity_code") or "").strip()
        name = (request.POST.get("entity_name") or "").strip()
        description = (request.POST.get("entity_description") or "").strip()
        entity = Entity.objects.select_related("entity_type").filter(id=entity_id).first() if entity_id else None
        entity_type = EntityType.objects.filter(id=entity_type_id, is_active=True).first() if entity_type_id else None
        category = Category.objects.filter(id=category_id, is_active=True).first() if category_id else None
        if not entity or not entity_type or not category or not name:
            messages.error(request, "Debe completar nombre, categoria y tipo de entidad.")
        else:
            entity.entity_type = entity_type
            entity.category = category
            entity.code = code
            entity.name = name
            entity.description = description
            entity.save(update_fields=["entity_type", "category", "code", "name", "description", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Entidad:{entity.entity_type.name}:{entity.name}",
                details="Entidad actualizada",
            )
            messages.success(request, "Entidad actualizada.")
        return redirect("structure:manage_levels")

    if action == "deactivate_entity":
        entity_id = request.POST.get("entity_id")
        entity = Entity.objects.select_related("entity_type").filter(id=entity_id).first() if entity_id else None
        if not entity:
            messages.error(request, "Entidad no encontrada.")
        else:
            entity.is_active = False
            entity.save(update_fields=["is_active", "updated_at"])
            record_action(
                "OTHER",
                request=request,
                module="structure",
                object_repr=f"Entidad:{entity.entity_type.name}:{entity.name}",
                details="Entidad desactivada",
            )
            messages.success(request, "Entidad desactivada.")
        return redirect("structure:manage_levels")

    sectors = Sector.objects.filter(is_active=True).order_by("name")
    subsectors = Subsector.objects.filter(is_active=True, sector__is_active=True).select_related("sector").order_by("sector__name", "name")
    categories = Category.objects.filter(is_active=True, subsector__is_active=True, subsector__sector__is_active=True).select_related("subsector", "subsector__sector").order_by(
        "subsector__sector__name", "subsector__name", "name"
    )
    sectors_all = Sector.objects.order_by("name")
    subsectors_all = Subsector.objects.select_related("sector").order_by("sector__name", "name")
    categories_all = Category.objects.select_related("subsector", "subsector__sector").order_by(
        "subsector__sector__name", "subsector__name", "name"
    )
    categories_active = Category.objects.filter(
        is_active=True,
        subsector__is_active=True,
        subsector__sector__is_active=True,
    ).select_related("subsector", "subsector__sector").order_by(
        "subsector__sector__name", "subsector__name", "name"
    )
    has_subsector = (
        Subsector.objects.filter(is_active=True, sector=current_sector).exists()
        if current_sector
        else False
    )
    has_category = (
        Category.objects.filter(is_active=True, subsector=current_subsector).exists()
        if current_subsector
        else False
    )
    entity_types_all = EntityType.objects.order_by("name")
    entity_types_active = EntityType.objects.filter(is_active=True).order_by("name")
    entities_all = Entity.objects.select_related(
        "entity_type",
        "category",
        "category__subsector",
        "category__subsector__sector",
    ).order_by("name")
    latest_entity = (
        Entity.objects.filter(category=current_category).select_related("entity_type").order_by("-created_at").first()
        if current_category
        else None
    )
    has_entity = (
        Entity.objects.filter(category=current_category, is_active=True).exists()
        if current_category
        else False
    )
    context = {
        "sectors": sectors,
        "subsectors": subsectors,
        "categories": categories,
        "sectors_all": sectors_all,
        "subsectors_all": subsectors_all,
        "categories_all": categories_all,
        "categories_active": categories_active,
        "entity_types_all": entity_types_all,
        "entity_types_active": entity_types_active,
        "entities_all": entities_all,
        "can_create_subsector": bool(current_sector),
        "can_create_category": bool(current_subsector),
        "can_assign_entities": categories.exists(),
        "can_create_entities": bool(current_category),
        "current_sector": current_sector,
        "current_subsector": current_subsector,
        "current_category": current_category,
        "latest_entity": latest_entity,
        "has_sector": bool(current_sector),
        "has_subsector": has_subsector,
        "has_category": has_category,
        "has_entity": has_entity,
        "sector_subsectors": Subsector.objects.filter(
            is_active=True, sector=current_sector
        ).order_by("name") if current_sector else Subsector.objects.none(),
        "subsector_categories": Category.objects.filter(
            is_active=True, subsector=current_subsector
        ).order_by("name") if current_subsector else Category.objects.none(),
    }
    return render(request, "structure/manage_levels.html", context)
