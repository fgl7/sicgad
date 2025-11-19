from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Membership


def admin_required(view_func):
    """
    Requiere que el usuario sea superuser o tenga Membership con rol ADMIN.
    """

    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if user.is_superuser:
            return view_func(request, *args, **kwargs)

        if Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists():
            return view_func(request, *args, **kwargs)

        return redirect("home")

    return _wrapped

