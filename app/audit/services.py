import uuid
from collections.abc import Mapping

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import AuditEvent

EVENT_MATRIX = {
    ("asset", "created"): {"success", "rejected", "failed"},
    ("asset", "updated"): {"success", "rejected", "failed"},
    ("asset", "status_changed"): {"success", "rejected", "failed"},
    ("asset", "deleted"): {"success", "rejected", "failed"},
    ("authentication", "login"): {"success", "failed"},
    ("authentication", "login_throttled"): {"rejected"},
    ("authentication", "logout"): {"success", "failed"},
    ("authentication", "password_changed"): {"success", "rejected", "failed"},
    ("account", "user_created"): {"success", "rejected", "failed"},
    ("account", "user_updated"): {"success", "rejected", "failed"},
    ("account", "user_disabled"): {"success", "rejected", "failed"},
    ("account", "role_changed"): {"success", "rejected", "failed"},
    ("account", "password_reset"): {"success", "rejected", "failed"},
    ("import", "previewed"): {"success", "rejected", "failed"},
    ("import", "executed"): {"started", "success", "partial", "failed", "interrupted"},
    ("export", "previewed"): {"success", "rejected", "failed"},
    ("export", "generated"): {"started", "success", "failed"},
    ("export", "downloaded"): {"started", "transferred", "failed", "interrupted"},
    ("backup", "created"): {"started", "success", "failed"},
    ("backup", "downloaded"): {"started", "transferred", "failed", "interrupted"},
    ("backup", "deleted"): {"success", "rejected", "failed"},
    ("restore", "validated"): {"success", "rejected", "failed"},
    ("restore", "restored"): {"started", "success", "aborted", "rolled_back", "recovery_required"},
    ("security", "authorization_denied"): {"denied"},
}

ALLOWED_FIELDS = frozenset({
    "name", "asset_no", "type", "purpose", "environment", "owner", "status", "room", "region",
    "hardware_text", "serial", "hostname", "supplier", "purchase_date", "rack_date", "warranty_end",
    "expires_on", "host_asset_no", "internal_ips", "external_ips", "display_name", "role", "active",
    "must_change_password", "changed", "error_code", "count", "format", "scope", "operation_uuid",
    "target_kind", "target_uuid", "asset_uuid", "event_uuid", "result", "source",
    "backup_id", "record_count", "q",
})
_FORBIDDEN_MARKERS = ("password", "password_hash", "token", "private_key", "credential_ref", "confirmation_id", "secret")


def _validate_value(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold()
            if any(marker in normalized for marker in _FORBIDDEN_MARKERS):
                raise ValueError("AUDIT_SECRET_FIELD")
            if normalized not in ALLOWED_FIELDS:
                raise ValueError("AUDIT_FIELD_NOT_ALLOWED")
            _validate_value(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_value(child)


def _event_content(event: AuditEvent) -> dict[str, object]:
    return {
        "instance_id": str(event.instance_id),
        "actor_uuid": str(event.actor_uuid) if event.actor_uuid else None,
        "actor_name_snapshot": event.actor_name_snapshot,
        "asset_uuid": str(event.asset_uuid) if event.asset_uuid else None,
        "asset_no_snapshot": event.asset_no_snapshot,
        "asset_name_snapshot": event.asset_name_snapshot,
        "category": event.category,
        "action": event.action,
        "result": event.result,
        "request_id": str(event.request_id) if event.request_id else None,
        "operation_uuid": str(event.operation_uuid) if event.operation_uuid else None,
        "before": event.before,
        "after": event.after,
        "summary": event.summary,
    }


def record_event(**fields):
    category = fields.get("category")
    action = fields.get("action")
    result = fields.get("result")
    if not isinstance(category, str) or not isinstance(action, str) or result not in EVENT_MATRIX.get((category, action), set()):
        raise ValueError("AUDIT_ENUM_INVALID")
    for field in ("before", "after", "summary"):
        value = fields.get(field) or {}
        if not isinstance(value, Mapping):
            raise ValueError("AUDIT_PAYLOAD_INVALID")
        _validate_value(value)
    fields.setdefault("event_uuid", uuid.uuid4())
    fields.setdefault("instance_id", uuid.UUID(settings.INSTANCE_ID))
    event_uuid = fields["event_uuid"]
    existing = AuditEvent.objects.filter(event_uuid=event_uuid).first()
    if existing is not None:
        if _event_content(existing) != _event_content(AuditEvent(**fields)):
            raise ValueError("AUDIT_EVENT_CONFLICT")
        return existing
    try:
        with transaction.atomic():
            return AuditEvent.objects.create(**fields)
    except IntegrityError as exc:
        existing = AuditEvent.objects.filter(event_uuid=event_uuid).first()
        if existing is None or _event_content(existing) != _event_content(AuditEvent(**fields)):
            raise ValueError("AUDIT_EVENT_CONFLICT") from exc
        return existing
