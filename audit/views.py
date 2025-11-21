from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import AuditLog


@login_required
def log_list(request):
    qs = AuditLog.objects.select_related("user").all()

    user_query = request.GET.get("user", "").strip()
    action = request.GET.get("action", "").strip()
    date_from = request.GET.get("from", "").strip()
    date_to = request.GET.get("to", "").strip()
    only_mine = request.GET.get("only_mine") == "1"

    if only_mine:
        qs = qs.filter(user=request.user)
    elif user_query:
        qs = qs.filter(username__icontains=user_query)

    if action:
        qs = qs.filter(action=action)

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    logs = qs.order_by("-created_at")[:500]

    return render(
        request,
        "audit/logs.html",
        {
            "logs": logs,
            "actions": AuditLog.ACTION_CHOICES,
            "filter_user": user_query,
            "filter_action": action,
            "filter_from": date_from,
            "filter_to": date_to,
            "only_mine": only_mine,
        },
    )
