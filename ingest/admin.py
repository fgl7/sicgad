from django.contrib import admin

from .models import DatasetInstance


@admin.register(DatasetInstance)
class DatasetInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "dataset_type",
        "plant",
        "period",
        "state",
        "row_count",
        "error_count",
        "created_at",
    )
    list_filter = ("state", "dataset_type__plant")
    search_fields = ("dataset_type__name", "plant__code")
