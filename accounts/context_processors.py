from .models import Membership


def admin_flags(request):
    user = getattr(request, "user", None)
    is_admin = False
    is_loader = False
    is_validator = False
    if user and user.is_authenticated:
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()
            is_loader = Membership.objects.filter(user=user, role="LOADER", is_active=True).exists()
            is_validator = Membership.objects.filter(
                user=user, role="VALIDATOR", is_active=True
            ).exists()

    return {
        "is_admin": is_admin,
        "is_loader": is_loader,
        "is_validator": is_validator,
    }
