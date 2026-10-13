from typing import cast

from common.authorization import require_roles
from common.errors import safe_error_code
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import User
from .services import authenticate_local, change_password, create_user
from .sessions import mark_session


def home_view(request: HttpRequest) -> HttpResponse:
    if getattr(request.user, "is_authenticated", False):
        if getattr(request.user, "must_change_password", False):
            return HttpResponseRedirect("/password")
        return HttpResponseRedirect("/assets")
    return HttpResponseRedirect("/login")


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_page(request: HttpRequest) -> HttpResponse:
    context: dict[str, object] = {}
    if request.method == "POST":
        user, throttled = authenticate_local(
            request.POST.get("username", ""),
            request.POST.get("password", ""),
        )
        if user is None:
            context["error"] = "登录失败，请检查用户名和密码" if not throttled else "登录暂停，请稍后再试"
        else:
            login(request, user, backend="accounts.backends.LocalBackend")
            mark_session(request.session, user)
            return HttpResponseRedirect("/password" if user.must_change_password else "/assets")
    return render(request, "accounts/login.html", context)


@require_http_methods(["POST"])
@require_roles("admin", "editor", "viewer")
def logout_page(request: HttpRequest) -> HttpResponse:
    logout(request)
    return HttpResponseRedirect("/login")


@csrf_protect
@require_http_methods(["GET", "POST"])
@require_roles("admin", "editor", "viewer")
def password_page(request: HttpRequest) -> HttpResponse:
    context: dict[str, object] = {}
    if request.method == "POST":
        user = cast(User, request.user)
        try:
            change_password(
                user,
                request.POST.get("current_password", ""),
                request.POST.get("new_password", ""),
            )
        except (TypeError, ValueError) as exc:
            context["error"] = safe_error_code(exc, "PASSWORD_INVALID")
        else:
            logout(request)
            context["success"] = "密码已修改，请重新登录"
    return render(request, "accounts/password.html", context)


@csrf_protect
@require_http_methods(["GET", "POST"])
@require_roles("admin")
def users_page(request: HttpRequest) -> HttpResponse:
    context: dict[str, object] = {"roles": User.Role.choices}
    if request.method == "POST":
        actor = cast(User, request.user)
        try:
            create_user(
                username=request.POST.get("username", ""),
                display_name=request.POST.get("display_name", ""),
                role=request.POST.get("role", ""),
                initial_password=request.POST.get("initial_password", ""),
                active=request.POST.get("active", "on") == "on",
                actor=actor,
            )
        except (TypeError, ValueError) as exc:
            context["error"] = safe_error_code(exc, "USER_FIELDS_INVALID")
        else:
            context["success"] = "账号已创建"
    context["users"] = User.objects.order_by("username_key")
    return render(request, "accounts/users.html", context)
