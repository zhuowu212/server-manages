import json

from audit.services import record_event
from common.authorization import require_roles
from common.errors import safe_error_code
from common.receipts import lookup_receipt, validate_idempotency_key
from common.responses import error_response
from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import User
from .serializers import public_user, validate_create
from .services import (
    CREATE_RECEIPT_KEYS,
    RESET_RECEIPT_KEYS,
    UPDATE_RECEIPT_KEYS,
    authenticate_local,
    change_password,
    create_confirmation,
    create_user,
    reset_user_password,
    update_user,
)
from .sessions import mark_session


def _body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _audit(**fields):
    try:
        return record_event(**fields)
    except Exception:
        return None


def _idempotency(request) -> str:
    value = request.headers.get("Idempotency-Key")
    return validate_idempotency_key(value)


@csrf_protect
@require_http_methods(["POST"])
def login_view(request):
    body = _body(request)
    if not isinstance(body, dict):
        return error_response(request, "INVALID_JSON", status=422)
    username, password = body.get("username"), body.get("password")
    user, throttled = authenticate_local(username or "", password or "")
    if user is None:
        if not _audit(category="authentication", action="login", result="failed", summary={"changed": False}):
            return error_response(request, "AUDIT_UNAVAILABLE", status=503)
        if throttled:
            if not _audit(category="authentication", action="login_throttled", result="rejected", summary={"changed": False}):
                return error_response(request, "AUDIT_UNAVAILABLE", status=503)
            return error_response(request, "THROTTLED", status=429, headers={"Retry-After": "900"})
        return error_response(request, "AUTHENTICATION_FAILED", status=401)
    if not _audit(category="authentication", action="login", result="success", actor_uuid=user.uuid, summary={"changed": True}):
        return error_response(request, "AUDIT_UNAVAILABLE", status=503)
    login(request, user, backend="accounts.backends.LocalBackend")
    mark_session(request.session, user)
    return JsonResponse({"id": str(user.uuid), "role": user.role, "must_change_password": user.must_change_password})


@require_http_methods(["POST"])
@require_roles("admin", "editor", "viewer")
def logout_view(request):
    record_event(category="authentication", action="logout", result="success", actor_uuid=request.user.uuid, summary={"changed": True})
    logout(request)
    return JsonResponse({}, status=204)


@csrf_protect
@require_http_methods(["POST"])
@require_roles("admin", "editor", "viewer")
def password_view(request):
    body = _body(request)
    try:
        change_password(request.user, body["current_password"], body["new_password"])
    except (KeyError, TypeError, ValueError) as exc:
        return error_response(request, safe_error_code(exc, "PASSWORD_INVALID"), status=422)
    logout(request)
    return JsonResponse({}, status=204)


@require_http_methods(["GET"])
@require_roles("admin", "editor", "viewer")
def me_view(request):
    user = request.user
    return JsonResponse({"id": str(user.uuid), "username": user.username, "role": user.role, "must_change_password": user.must_change_password})


@csrf_protect
@require_http_methods(["GET", "POST"])
@require_roles("admin")
def users_collection_view(request):
    if request.method == "GET":
        page = request.GET.get("page", "1")
        page_size = request.GET.get("page_size", "25")
        try:
            page_number, size = int(page), int(page_size)
            if page_number < 1 or not 1 <= size <= 100:
                raise ValueError
        except ValueError:
            return error_response(request, "PAGINATION_INVALID", status=422)
        queryset = User.objects.order_by("username_key")
        total = queryset.count()
        start = (page_number - 1) * size
        return JsonResponse({"items": [public_user(user) for user in queryset[start:start + size]], "total": total, "page": page_number, "page_size": size})
    body = _body(request)
    try:
        if not isinstance(body, dict):
            raise ValueError("USER_FIELDS_INVALID")
        idem = _idempotency(request)
        receipt_payload = {"route": "user_create", **body}
        prior, replayed = lookup_receipt(
            actor_uuid=request.user.uuid, idempotency_key=idem,
            payload=receipt_payload, allowed_keys=CREATE_RECEIPT_KEYS,
        )
        if replayed and prior:
            response = JsonResponse(prior.result_ref or {}, status=201)
            response["Idempotency-Replayed"] = "true"
            return response
        validate_create(body)
        user = create_user(
            active=body.get("active", True), username=body["username"],
            display_name=body["display_name"], role=body["role"],
            initial_password=body["initial_password"], actor=request.user,
            idempotency_key=idem, request_payload=receipt_payload,
        )
        result = {"id": str(user.uuid), "version": user.version}
    except (TypeError, ValueError) as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=409 if code in {"USERNAME_CONFLICT", "IDEMPOTENCY_CONFLICT"} else 422)
    return JsonResponse(result, status=201)


@csrf_protect
@require_http_methods(["POST"])
@require_roles("admin")
def user_preview_view(request, user_id):
    target = User.objects.filter(uuid=user_id).first()
    body = _body(request)
    if not target or not isinstance(body, dict):
        return error_response(request, "INVALID_INPUT", status=422)
    actions = body.get("actions")
    changes = body.get("changes", {})
    if not isinstance(actions, list) or not actions or any(not isinstance(action, str) for action in actions):
        return error_response(request, "ACTIONS_INVALID", status=422)
    if not isinstance(changes, dict):
        return error_response(request, "RESET_CHANGES_INVALID", status=422)
    try:
        raw = create_confirmation(actor=request.user, target=target, actions=actions, proposed_changes=changes)
    except ValueError as exc:
        return error_response(request, safe_error_code(exc), status=422)
    except Exception:
        return error_response(request, "CONFIRMATION_FAILED", status=503)
    return JsonResponse({"confirmation_id": raw, "target_version": target.version, "actions": sorted(actions)})


@csrf_protect
@require_http_methods(["PATCH"])
@require_roles("admin")
def user_update_view(request, user_id):
    target = User.objects.filter(uuid=user_id).first()
    body = _body(request)
    if not target or not isinstance(body, dict):
        return error_response(request, "INVALID_INPUT", status=422)
    try:
        idem = _idempotency(request)
        receipt_payload = {"route": "user_update", "target_uuid": str(target.uuid), **body}
        prior, replayed = lookup_receipt(
            actor_uuid=request.user.uuid, idempotency_key=idem,
            payload=receipt_payload, allowed_keys=UPDATE_RECEIPT_KEYS,
        )
        if replayed and prior:
            response = JsonResponse(prior.result_ref or {}, status=200)
            response["Idempotency-Replayed"] = "true"
            return response
    except ValueError as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=409 if code == "IDEMPOTENCY_CONFLICT" else 422)
    if "username" in body or "username_key" in body:
        return error_response(request, "USERNAME_IMMUTABLE", status=422)
    fields = {key for key in body if key not in {"version", "confirmation_id", "display_name", "role", "active"}}
    if fields or not isinstance(body.get("version"), int):
        return error_response(request, "FIELDS_INVALID", status=422)
    try:
        target = update_user(
            actor=request.user, target=target, version=body["version"],
            display_name=body.get("display_name"), role=body.get("role"),
            active=body.get("active"), confirmation=body.get("confirmation_id"),
            idempotency_key=idem, request_payload=receipt_payload,
        )
    except (ValueError, TypeError) as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=409 if code in {"STALE_VERSION", "CONFIRMATION_MISMATCH", "CONFIRMATION_INVALID", "LAST_ADMIN_PROTECTED"} else 422)
    return JsonResponse(public_user(target))


@csrf_protect
@require_http_methods(["POST"])
@require_roles("admin")
def user_reset_password_view(request, user_id):
    target = User.objects.filter(uuid=user_id).first()
    body = _body(request)
    if not target or not isinstance(body, dict):
        return error_response(request, "INVALID_INPUT", status=422)
    try:
        idem = _idempotency(request)
        receipt_payload = {"route": "password_reset", "target_uuid": str(target.uuid), **body}
        prior, replayed = lookup_receipt(
            actor_uuid=request.user.uuid, idempotency_key=idem,
            payload=receipt_payload, allowed_keys=RESET_RECEIPT_KEYS,
        )
        if replayed and prior:
            response = JsonResponse(prior.result_ref or {}, status=200)
            response["Idempotency-Replayed"] = "true"
            return response
    except ValueError as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=409 if code == "IDEMPOTENCY_CONFLICT" else 422)
    try:
        target = reset_user_password(
            actor=request.user, target=target, version=body["version"],
            new_password=body["new_password"], confirmation=body["confirmation_id"],
            idempotency_key=idem, request_payload=receipt_payload,
        )
    except (KeyError, TypeError, ValueError) as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=409 if code in {"STALE_VERSION", "CONFIRMATION_MISMATCH", "CONFIRMATION_INVALID"} else 422)
    return JsonResponse(public_user(target))
