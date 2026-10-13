from common.responses import error_response

from .sessions import session_is_current, touch_session


class ForcePasswordChangeMiddleware:
    allowed = ("/api/v1/auth/password", "/api/v1/auth/logout", "/api/v1/auth/me", "/health/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            if "_session_created_at" not in request.session:
                return error_response(request, "SESSION_INVALID", status=401)
            elif not session_is_current(request.session, user):
                return error_response(request, "SESSION_INVALID", status=401)
            else:
                touch_session(request.session, user)
        if getattr(user, "is_authenticated", False) and getattr(user, "must_change_password", False):
            if not any(request.path.startswith(path) for path in self.allowed):
                return error_response(request, "PASSWORD_CHANGE_REQUIRED", status=403, message="请先修改密码")
        return self.get_response(request)
