from .models import AuditLog


def record_action(action, request=None, module="", object_repr="", details=""):
    user = None
    username = ""
    if request and getattr(request, "user", None) and request.user.is_authenticated:
        user = request.user
        username = request.user.get_username()
    elif request and getattr(request, "user", None) and request.user.is_anonymous:
        username = "Anonymous"

    AuditLog.objects.create(
        user=user,
        username=username,
        action=action,
        module=module,
        object_repr=object_repr,
        details=details,
    )
