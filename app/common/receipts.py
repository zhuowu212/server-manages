import hashlib
import json
import uuid
from typing import Any

from django.db import IntegrityError, transaction
from operations.control_models import ControlReceipt

from .models import OperationReceipt

SENSITIVE_KEYS = {
    "password", "password_hash", "token", "private_key", "credential_ref",
    "confirmation_id", "candidate_admin_username", "candidate_admin_password",
    "current_password", "new_password", "initial_password",
}


def _public(value: Any, *, allowed_keys: frozenset[str] | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _public(child)
            for key, child in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).casefold() not in SENSITIVE_KEYS
            and (allowed_keys is None or str(key) in allowed_keys)
        }
    if isinstance(value, (list, tuple)):
        return [_public(child) for child in value]
    return value


def request_digest(payload: dict[str, object], *, allowed_keys: frozenset[str] | None = None) -> str:
    safe = _public(payload, allowed_keys=allowed_keys)
    encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_idempotency_key(value: str | None) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or any(ord(char) < 0x20 for char in value):
        raise ValueError("IDEMPOTENCY_KEY_INVALID")
    return value


class IdempotencyConflict(ValueError):
    code = "IDEMPOTENCY_CONFLICT"


def lookup_receipt(
    *, actor_uuid: uuid.UUID, idempotency_key: str, payload: dict[str, object],
    using: str = "default", allowed_keys: frozenset[str] | None = None,
) -> tuple[OperationReceipt | None, bool]:
    """Return a prior receipt and whether it is a replay.

    The lookup happens after authorization and before version/confirmation
    validation, so a completed retry remains observable even if its secret
    fields differ in the new request.
    """
    digest = request_digest(payload, allowed_keys=allowed_keys)
    receipt = OperationReceipt.objects.using(using).filter(actor_uuid=actor_uuid, idempotency_key=idempotency_key).first()
    if receipt is None:
        return None, False
    if receipt.request_digest != digest:
        raise IdempotencyConflict("IDEMPOTENCY_CONFLICT")
    return receipt, True


def save_receipt(
    *, actor_uuid: uuid.UUID, idempotency_key: str, payload: dict[str, object],
    operation_uuid: uuid.UUID | None = None, confirmation_uuid: uuid.UUID | None = None,
    result_ref: dict[str, object] | None = None, using: str = "default",
    allowed_keys: frozenset[str] | None = None,
) -> OperationReceipt:
    operation_uuid = operation_uuid or uuid.uuid4()
    digest = request_digest(payload, allowed_keys=allowed_keys)
    try:
        with transaction.atomic(using=using):
            receipt = OperationReceipt.objects.using(using).create(
                uuid=uuid.uuid4(), actor_uuid=actor_uuid, idempotency_key=idempotency_key,
                operation_uuid=operation_uuid, request_digest=digest,
                confirmation_uuid=confirmation_uuid, result_ref=result_ref,
            )
    except IntegrityError:
        receipt = OperationReceipt.objects.using(using).get(actor_uuid=actor_uuid, idempotency_key=idempotency_key)
        if receipt.request_digest != digest:
            raise IdempotencyConflict("IDEMPOTENCY_CONFLICT") from None
    return receipt


def save_control_receipt(
    *, actor_uuid: uuid.UUID, idempotency_key: str, payload: dict[str, object],
    operation_uuid: uuid.UUID | None = None, confirmation_uuid: uuid.UUID | None = None,
    result_ref: dict[str, object] | None = None,
    allowed_keys: frozenset[str] | None = None,
) -> ControlReceipt:
    operation_uuid = operation_uuid or uuid.uuid4()
    digest = request_digest(payload, allowed_keys=allowed_keys)
    try:
        with transaction.atomic(using="control"):
            receipt = ControlReceipt.objects.using("control").create(  # type: ignore[attr-defined]
                uuid=uuid.uuid4(), actor_uuid=actor_uuid, idempotency_key=idempotency_key,
                operation_uuid=operation_uuid, request_digest=digest,
                confirmation_uuid=confirmation_uuid, result_ref=result_ref,
            )
    except IntegrityError:
        receipt = ControlReceipt.objects.using("control").get(actor_uuid=actor_uuid, idempotency_key=idempotency_key)  # type: ignore[attr-defined]
        if receipt.request_digest != digest:
            raise IdempotencyConflict("IDEMPOTENCY_CONFLICT") from None
    return receipt
