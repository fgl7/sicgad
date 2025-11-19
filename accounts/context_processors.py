from .models import Membership


def admin_flags(request):
    user = getattr(request, "user", None)
    is_admin = False
    if user and user.is_authenticated:
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()

    return {
        "is_admin": is_admin,
    }

