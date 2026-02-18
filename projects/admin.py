from django.contrib import admin

from .models import Project, ProjectReportConfig


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "entities_display", "executor", "is_active")
    list_filter = ("is_active", "entities")
    search_fields = ("name", "code", "executor", "location")
    filter_horizontal = ("entities",)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("entities")

    @admin.display(description="Entidades")
    def entities_display(self, obj):
        return ", ".join(obj.entities.values_list("code", flat=True)) or "-"


@admin.register(ProjectReportConfig)
class ProjectReportConfigAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "name",
        "report_dataset",
        "curve_program_dataset",
        "curve_executed_dataset",
        "is_active",
    )
    list_filter = (
        "is_active",
        "project",
        "curve_executed_dataset__validation_frequency",
    )
    search_fields = (
        "name",
        "project__name",
        "project__code",
        "report_dataset__name",
        "curve_program_dataset__name",
        "curve_executed_dataset__name",
    )
    autocomplete_fields = (
        "project",
        "report_dataset",
        "curve_program_dataset",
        "curve_executed_dataset",
    )
