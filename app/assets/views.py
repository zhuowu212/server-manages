from __future__ import annotations

import json

from audit.services import record_event
from common.authorization import require_roles
from common.errors import safe_error_code
from common.receipts import IdempotencyConflict, lookup_receipt, validate_idempotency_key
from common.responses import error_response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import Asset
from .selectors import asset_list
from .serializers import public_asset
from .services import (
    ASSET_RECEIPT_KEYS,
    AssetAuthorizationError,
    create_asset,
    delete_asset,
    preview_delete_asset,
    update_asset,
)

CONFLICT_CODES = {
    "ASSET_NO_CONFLICT",
    "SERIAL_CONFLICT",
    "HOSTNAME_CONFLICT",
    "IP_CONFLICT",
    "INVALID_HOST",
    "STALE_VERSION",
    "DEPENDENCY_CONFLICT",
    "CONFIRMATION_INVALID",
    "CONFIRMATION_MISMATCH",
    "IDEMPOTENCY_CONFLICT",
}


def _body(request) -> dict[str, object] | None:
    try:
        value = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _version(request, body: dict[str, object]) -> int:
    value = request.headers.get("If-Match") or body.get("version")
    if isinstance(value, str):
        value = value.strip('"')
        if value.isdecimal():
            return int(value)
    if isinstance(value, int):
        return value
    raise ValueError("VERSION_REQUIRED")


def _status(code: str) -> int:
    return 409 if code in CONFLICT_CODES else 422


def _deny(request, *, target_uuid: str | None = None) -> JsonResponse:
    try:
        record_event(
            category="security",
            action="authorization_denied",
            result="denied",
            actor_uuid=request.user.uuid,
            actor_name_snapshot=request.user.display_name,
            summary={"target_kind": "assets", "target_uuid": target_uuid or "", "changed": False},
        )
    except Exception:
        return error_response(request, "AUDIT_UNAVAILABLE", status=503)
    return error_response(request, "FORBIDDEN", status=403)


@csrf_protect
@require_http_methods(["GET", "POST"])
@require_roles("admin", "editor", "viewer")
def assets_collection_view(request):
    if request.method == "GET":
        try:
            return JsonResponse(asset_list(request.GET))
        except ValueError as exc:
            return error_response(request, safe_error_code(exc), status=422)
    if request.user.role not in {"admin", "editor"}:
        return _deny(request)
    body = _body(request)
    if body is None:
        return error_response(request, "INVALID_JSON", status=422)
    try:
        idem = validate_idempotency_key(request.headers.get("Idempotency-Key"))
        receipt_payload = {"route": "asset_create", **body}
        prior, replayed = lookup_receipt(
            actor_uuid=request.user.uuid,
            idempotency_key=idem,
            payload=receipt_payload,
            allowed_keys=ASSET_RECEIPT_KEYS,
        )
        if replayed and prior:
            response = JsonResponse(prior.result_ref or {}, status=201)
            response["Idempotency-Replayed"] = "true"
            return response
        asset = create_asset(actor=request.user, payload=body, idempotency_key=idem, receipt_payload=receipt_payload)
    except AssetAuthorizationError:
        return _deny(request)
    except (IdempotencyConflict, ValueError) as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=_status(code))
    return JsonResponse({"id": str(asset.uuid), "version": asset.version}, status=201)


@csrf_protect
@require_http_methods(["GET", "PATCH", "DELETE"])
@require_roles("admin", "editor", "viewer")
def asset_detail_view(request, asset_id):
    if request.method == "DELETE":
        return asset_delete_view(request, asset_id)
    asset = Asset.objects.select_related("identity", "host", "host__identity").prefetch_related("addresses").filter(uuid=asset_id).first()
    if asset is None:
        return error_response(request, "NOT_FOUND", status=404)
    if request.method == "GET":
        return JsonResponse(public_asset(asset))
    body = _body(request)
    if body is None:
        return error_response(request, "INVALID_JSON", status=422)
    try:
        idem = validate_idempotency_key(request.headers.get("Idempotency-Key"))
        version = _version(request, body)
        receipt_payload = {"route": "asset_update", "target_uuid": str(asset.uuid), "version": version, **body}
        prior, replayed = lookup_receipt(
            actor_uuid=request.user.uuid,
            idempotency_key=idem,
            payload=receipt_payload,
            allowed_keys=ASSET_RECEIPT_KEYS,
        )
        if replayed and prior:
            response = JsonResponse(prior.result_ref or {}, status=200)
            response["Idempotency-Replayed"] = "true"
            return response
        asset = update_asset(
            actor=request.user,
            asset=asset,
            version=version,
            payload=body,
            idempotency_key=idem,
            receipt_payload=receipt_payload,
        )
    except AssetAuthorizationError:
        return _deny(request, target_uuid=str(asset.uuid))
    except (IdempotencyConflict, ValueError) as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=_status(code))
    return JsonResponse(public_asset(asset))


@csrf_protect
@require_http_methods(["POST"])
@require_roles("admin", "editor", "viewer")
def asset_delete_preview_view(request, asset_id):
    asset = Asset.objects.select_related("identity").prefetch_related("virtual_children").filter(uuid=asset_id).first()
    if asset is None:
        return error_response(request, "NOT_FOUND", status=404)
    try:
        return JsonResponse(preview_delete_asset(actor=request.user, asset=asset))
    except AssetAuthorizationError:
        return _deny(request, target_uuid=str(asset.uuid))
    except ValueError as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=_status(code))


@csrf_protect
@require_http_methods(["DELETE"])
@require_roles("admin", "editor", "viewer")
def asset_delete_view(request, asset_id):
    body = _body(request)
    if body is None:
        return error_response(request, "INVALID_JSON", status=422)
    try:
        idem = validate_idempotency_key(request.headers.get("Idempotency-Key"))
        version = _version(request, body)
        receipt_payload = {"route": "asset_delete", "target_uuid": str(asset_id), "version": version}
        prior, replayed = lookup_receipt(
            actor_uuid=request.user.uuid,
            idempotency_key=idem,
            payload=receipt_payload,
            allowed_keys=ASSET_RECEIPT_KEYS,
        )
        if replayed and prior:
            response = JsonResponse({}, status=204)
            response["Idempotency-Replayed"] = "true"
            return response
        asset = Asset.objects.select_related("identity").prefetch_related("addresses").filter(uuid=asset_id).first()
        if asset is None:
            return error_response(request, "NOT_FOUND", status=404)
        confirmation = body.get("confirmation_id")
        if not isinstance(confirmation, str):
            raise ValueError("CONFIRMATION_REQUIRED")
        delete_asset(
            actor=request.user,
            asset=asset,
            version=version,
            confirmation=confirmation,
            idempotency_key=idem,
            receipt_payload=receipt_payload,
        )
    except AssetAuthorizationError:
        return _deny(request, target_uuid=str(asset_id))
    except (IdempotencyConflict, ValueError) as exc:
        code = safe_error_code(exc)
        return error_response(request, code, status=_status(code))
    return JsonResponse({}, status=204)
