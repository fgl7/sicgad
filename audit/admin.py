from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "module", "object_repr", "username")
    list_filter = ("action", "module", "created_at")
    search_fields = ("username", "object_repr", "details")
    ordering = ("-created_at",)
