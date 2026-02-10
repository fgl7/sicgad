from django.contrib import admin

from .models import Category, Entity, Sector, Subsector


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(Subsector)
class SubsectorAdmin(admin.ModelAdmin):
    list_display = ("name", "sector", "is_active", "updated_at")
    list_filter = ("is_active", "sector")
    search_fields = ("name", "description", "sector__name")
    autocomplete_fields = ("sector",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "subsector", "is_active", "updated_at")
    list_filter = ("is_active", "subsector__sector")
    search_fields = ("name", "description", "subsector__name", "subsector__sector__name")
    autocomplete_fields = ("subsector",)


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "code", "is_active", "updated_at")
    list_filter = ("is_active", "category__subsector__sector")
    search_fields = (
        "name",
        "code",
        "description",
        "category__name",
        "category__subsector__name",
        "category__subsector__sector__name",
    )
    autocomplete_fields = ("category",)
