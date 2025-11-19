from django.shortcuts import render

from accounts.models import Membership


def landing(request):
    return render(request, "landing.html")


def home(request):
    user = request.user
    is_admin = False
    if user.is_authenticated:
        if user.is_superuser:
            is_admin = True
        else:
            is_admin = Membership.objects.filter(user=user, role="ADMIN", is_active=True).exists()

    return render(request, "kpis/home.html", {"is_admin": is_admin})
