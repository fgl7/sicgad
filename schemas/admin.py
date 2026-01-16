from django.contrib import admin

from .models import ColumnDef, DatasetType


class ColumnDefInline(admin.TabularInline):
    model = ColumnDef
    extra = 0


@admin.register(DatasetType)
class DatasetTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "plant",
        "project",
        "version",
        "validation_frequency",
        "is_one_time",
        "is_certification",
        "status",
        "is_active",
    )
    list_filter = (
        "plant",
        "project",
        "validation_frequency",
        "is_one_time",
        "is_certification",
        "status",
        "is_active",
    )
    search_fields = ("name", "plant__code", "plant__name", "project__code", "project__name")
    autocomplete_fields = ("plant", "project", "source_dataset")
    inlines = [ColumnDefInline]


@admin.register(ColumnDef)
class ColumnDefAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "label",
        "dataset_type",
        "data_type",
        "axis_role",
        "default_agg",
        "is_primary_kpi",
        "is_active",
    )
    list_filter = (
        "data_type",
        "axis_role",
        "is_active",
        "dataset_type__plant",
        "dataset_type__project",
    )
    search_fields = (
        "name",
        "label",
        "dataset_type__name",
        "dataset_type__plant__code",
        "dataset_type__project__code",
        "dataset_type__project__name",
    )
