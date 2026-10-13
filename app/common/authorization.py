from functools import wraps

from audit.services import record_event
from django.http import JsonResponse

from common.responses import error_response


def _denied(request, *, category: str = "unknown") -> JsonResponse:
    """Record one non-recursive authorization event and return a safe 403."""
    try:
        user = request.user
        record_event(
            category="security", action="authorization_denied", result="denied",
            actor_uuid=getattr(user, "uuid", None),
            actor_name_snapshot="", summary={"target_kind": category, "changed": False},
        )
    except Exception:
        return error_response(request, "AUDIT_UNAVAILABLE", status=503)
    return error_response(request, "FORBIDDEN", status=403)


def require_roles(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not getattr(user, "is_authenticated", False):
                return error_response(request, "UNAUTHENTICATED", status=401)
            if not getattr(user, "active", False) or getattr(user, "role", None) not in roles:
                return _denied(request, category=request.path.split("/")[3] if len(request.path.split("/")) > 3 else "unknown")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
