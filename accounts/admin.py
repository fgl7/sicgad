from django.contrib import admin

from .models import AccountProfile, Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "plant", "role", "institution", "validation_level", "can_validate_daily", "can_validate_monthly", "is_active")
    list_filter = ("role", "institution", "is_active", "plant", "can_validate_daily", "can_validate_monthly")
    search_fields = ("user__username", "user__email", "plant__code", "plant__name")


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "must_change_password")
    list_filter = ("must_change_password",)
    search_fields = ("user__username", "user__email")
