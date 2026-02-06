from django.contrib import admin

from .models import AccountProfile, Institution, Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "entity",
        "role",
        "institution",
        "validation_level",
        "can_validate_daily",
        "can_validate_weekly",
        "can_validate_projections",
        "can_validate_monthly",
        "is_active",
    )
    list_filter = (
        "role",
        "institution",
        "is_active",
        "entity",
        "can_validate_daily",
        "can_validate_weekly",
        "can_validate_projections",
        "can_validate_monthly",
    )
    search_fields = (
        "user__username",
        "user__email",
        "entity__code",
        "entity__name",
    )


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "must_change_password")
    list_filter = ("must_change_password",)
    search_fields = ("user__username", "user__email")


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
