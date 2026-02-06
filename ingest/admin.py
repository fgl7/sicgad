from django.contrib import admin

from .models import (
    DatasetChangeAttachment,
    DatasetChangeRequest,
    DatasetInstance,
    HistoricalImportBatch,
    PublishedDataPoint,
)


@admin.register(DatasetInstance)
class DatasetInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "dataset_type",
        "entity",
        "period",
        "state",
        "row_count",
        "error_count",
        "created_by",
        "submitted_at",
        "created_at",
    )
    list_filter = (
        "state",
        "dataset_type__entity",
        "dataset_type__validation_frequency",
        "dataset_type__is_one_time",
        "entity",
    )
    search_fields = (
        "dataset_type__name",
        "entity__code",
        "entity__name",
    )
    autocomplete_fields = ("dataset_type", "entity", "created_by")
    date_hierarchy = "period"


@admin.register(PublishedDataPoint)
class PublishedDataPointAdmin(admin.ModelAdmin):
    list_display = (
        "instance",
        "column",
        "row_index",
        "numeric_value",
        "text_value",
        "date_value",
        "bool_value",
    )
    list_filter = ("column",)
    search_fields = ("instance__dataset_type__name", "column__name", "column__label")
    autocomplete_fields = ("instance", "column")


@admin.register(DatasetChangeRequest)
class DatasetChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("instance", "submitted_by", "target_instance", "target_period", "created_at")
    list_filter = ("target_period", "created_at")
    search_fields = ("instance__dataset_type__name", "submitted_by__user__username")
    autocomplete_fields = ("instance", "submitted_by", "target_instance")


@admin.register(DatasetChangeAttachment)
class DatasetChangeAttachmentAdmin(admin.ModelAdmin):
    list_display = ("request", "original_name", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("original_name", "request__instance__dataset_type__name")
    autocomplete_fields = ("request",)


@admin.register(HistoricalImportBatch)
class HistoricalImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "dataset_type",
        "entity",
        "status",
        "created_by",
        "created_at",
        "finished_at",
        "total_rows",
        "created_instances",
        "updated_instances",
        "skipped_instances",
    )
    list_filter = ("status", "entity", "created_at")
    search_fields = ("dataset_type__name", "entity__code", "entity__name")
    autocomplete_fields = ("dataset_type", "entity", "created_by")
