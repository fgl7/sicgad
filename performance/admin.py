from django.contrib import admin

from .models import (
    PerformanceIndicator,
    PerformanceIndicatorInput,
    PerformanceIndicatorResult,
    PerformanceVariable,
    PerformanceVariableMapping,
)


@admin.register(PerformanceVariable)
class PerformanceVariableAdmin(admin.ModelAdmin):
    list_display = ("key", "plant", "label", "unit", "value_type", "is_active", "updated_at")
    list_filter = ("plant", "value_type", "is_active")
    search_fields = ("key", "label", "description", "plant__code", "plant__name")


@admin.register(PerformanceVariableMapping)
class PerformanceVariableMappingAdmin(admin.ModelAdmin):
    list_display = (
        "variable",
        "dataset_type",
        "column",
        "aggregation",
        "transform",
        "transform_value",
        "offset_months",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "aggregation", "transform", "dataset_type__entity")
    search_fields = (
        "variable__key",
        "variable__label",
        "dataset_type__name",
        "dataset_type__slug",
        "column__name",
        "column__label",
    )
    autocomplete_fields = ("variable", "dataset_type", "column")


@admin.register(PerformanceIndicator)
class PerformanceIndicatorAdmin(admin.ModelAdmin):
    list_display = ("key", "plant", "label", "unit", "is_active", "updated_at")
    list_filter = ("plant", "is_active")
    search_fields = ("key", "label", "description", "formula_text", "plant__code", "plant__name")
    filter_horizontal = ("variables",)


@admin.register(PerformanceIndicatorInput)
class PerformanceIndicatorInputAdmin(admin.ModelAdmin):
    list_display = ("indicator", "token", "column", "aggregation", "is_active", "updated_at")
    list_filter = ("aggregation", "is_active", "indicator__plant")
    search_fields = ("indicator__key", "token", "column__name", "column__label")
    autocomplete_fields = ("indicator", "column")


@admin.register(PerformanceIndicatorResult)
class PerformanceIndicatorResultAdmin(admin.ModelAdmin):
    list_display = ("indicator", "plant", "period_end", "frequency", "status")
    list_filter = ("frequency", "status", "stage", "plant")
    search_fields = ("indicator__key", "plant__code", "plant__name")
    ordering = ("-period_end",)

# Register your models here.
