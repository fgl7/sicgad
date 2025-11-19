from django.contrib import admin

from .models import ValidationAction


@admin.register(ValidationAction)
class ValidationActionAdmin(admin.ModelAdmin):
    list_display = ("dataset_instance", "level", "decision", "user", "created_at")
    list_filter = ("decision", "level")
    search_fields = ("dataset_instance__dataset_type__name",)
