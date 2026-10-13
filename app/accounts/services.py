from __future__ import annotations

import uuid
from datetime import timedelta

from audit.services import record_event
from common.confirmations import issue_token, token_digest
from common.errors import AuditUnavailable
from common.models import ChangeConfirmation
from common.receipts import save_receipt
from django.db import IntegrityError, transaction
from django.utils import timezone
from operations.gate import current_epoch

from .models import LoginAttemptState, User
from .passwords import hash_password, validate_password, verify_password_equalized


def _record_event(**fields):
    try:
        return record_event(**fields)
    except Exception as exc:
        raise AuditUnavailable() from exc


def authenticate_local(username: str, password: str) -> tuple[User | None, bool]:
    key = username.strip().casefold() if isinstance(username, str) else ""
    password = password if isinstance(password, str) else ""
    now = timezone.now()
    candidate = User.objects.filter(username_key=key).first()
    verified = verify_password_equalized(candidate.password_hash if candidate else None, password)
    with transaction.atomic():
        state, _ = LoginAttemptState.objects.select_for_update().get_or_create(
            normalized_login_key=key, defaults={"window_start": now}
        )
        if state.locked_until and state.locked_until > now:
            return None, True
        user = User.objects.filter(username_key=key).first()
        valid = bool(
            user and candidate and user.password_hash == candidate.password_hash
            and user.active and verified
        )
        if valid:
            state.consecutive_failures = 0
            state.locked_until = None
            state.window_start = now
            state.save(update_fields=["consecutive_failures", "locked_until", "window_start"])
            return user, False
        if now - state.window_start >= timedelta(minutes=15):
            state.window_start, state.consecutive_failures = now, 0
        state.consecutive_failures += 1
        if state.consecutive_failures >= 5:
            state.locked_until = now + timedelta(minutes=15)
        state.save(update_fields=["window_start", "consecutive_failures", "locked_until"])
        return None, bool(state.locked_until and state.locked_until > now)


CREATE_RECEIPT_KEYS = frozenset({"route", "username", "display_name", "role", "active"})
UPDATE_RECEIPT_KEYS = frozenset({"route", "target_uuid", "version", "display_name", "role", "active"})
RESET_RECEIPT_KEYS = frozenset({"route", "target_uuid", "version"})


def _public_user_payload(user: User) -> dict[str, object]:
    return {
        "id": str(user.uuid),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "active": user.active,
        "must_change_password": user.must_change_password,
        "version": user.version,
    }


def create_user(
    *, username: str, display_name: str, role: str, initial_password: str,
    active: bool = True, actor: User | None = None, idempotency_key: str | None = None,
    request_payload: dict[str, object] | None = None,
) -> User:
    username = username.strip() if isinstance(username, str) else ""
    display_name = display_name.strip() if isinstance(display_name, str) else ""
    if not 1 <= len(username) <= 128 or not 1 <= len(display_name) <= 128 or role not in User.Role.values or not isinstance(active, bool):
        raise ValueError("USER_FIELDS_INVALID")
    validate_password(initial_password)
    key = username.casefold()
    if User.objects.filter(username_key=key).exists():
        raise ValueError("USERNAME_CONFLICT")
    password_hash = hash_password(initial_password)
    with transaction.atomic():
        try:
            user = User.objects.create(
                username=username, username_key=key, display_name=display_name, role=role,
                active=active, must_change_password=True, password_hash=password_hash,
            )
        except IntegrityError as exc:
            raise ValueError("USERNAME_CONFLICT") from exc
        operation_uuid = uuid.uuid4()
        _record_event(
            category="account", action="user_created", result="success",
            actor_uuid=actor.uuid if actor else None, operation_uuid=operation_uuid,
            summary={"changed": True, "target_uuid": str(user.uuid)},
        )
        if actor is not None and idempotency_key and request_payload is not None:
            save_receipt(
                actor_uuid=actor.uuid, idempotency_key=idempotency_key,
                payload=request_payload, operation_uuid=operation_uuid,
                result_ref={"id": str(user.uuid), "version": user.version},
                allowed_keys=CREATE_RECEIPT_KEYS,
            )
    return user


def change_password(user: User, current_password: str, new_password: str) -> User:
    expected_hash = user.password_hash
    if not isinstance(current_password, str) or not isinstance(new_password, str) or not verify_password_equalized(expected_hash, current_password):
        raise ValueError("CURRENT_PASSWORD_INVALID")
    validate_password(new_password)
    password_hash = hash_password(new_password)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.password_hash != expected_hash:
            raise ValueError("CURRENT_PASSWORD_INVALID")
        user.password_hash = password_hash
        user.must_change_password = False
        user.version += 1
        user.auth_version += 1
        user.save(update_fields=["password_hash", "must_change_password", "version", "auth_version"])
        _record_event(category="authentication", action="password_changed", result="success", actor_uuid=user.uuid, summary={"changed": True})
        return user


def create_confirmation(*, actor: User, target: User, actions: list[str], proposed_changes: dict[str, object]) -> str:
    allowed = {"disable", "change_role", "reset_password"}
    actions = sorted(set(actions))
    if not actions or any(action not in allowed for action in actions) or ("reset_password" in actions and len(actions) != 1):
        raise ValueError("ACTIONS_INVALID")
    if not isinstance(proposed_changes, dict):
        raise ValueError("CONFIRMATION_FIELDS_INVALID")
    if "reset_password" in actions and proposed_changes:
        raise ValueError("CONFIRMATION_FIELDS_INVALID")
    if "disable" in actions and proposed_changes.get("active") is not False:
        raise ValueError("CONFIRMATION_FIELDS_INVALID")
    if "change_role" in actions and (
        not isinstance(proposed_changes.get("role"), str)
        or proposed_changes.get("role") not in User.Role.values
        or proposed_changes.get("role") == target.role
    ):
        raise ValueError("CONFIRMATION_FIELDS_INVALID")
    expected_fields = {"active"} if actions == ["disable"] else {"role"} if actions == ["change_role"] else {"active", "role"} if set(actions) == {"change_role", "disable"} else set()
    if set(proposed_changes) != expected_fields:
        raise ValueError("CONFIRMATION_FIELDS_INVALID")
    raw, digest = issue_token()
    epoch = current_epoch()
    with transaction.atomic():
        ChangeConfirmation.objects.create(
            uuid=uuid.uuid4(), token_digest=digest, actor_uuid=actor.uuid,
            actor_auth_version=actor.auth_version, session_epoch=epoch, target_kind="user",
            target_uuid=target.uuid, target_version=target.version,
            actions=sorted(actions), proposed_changes=proposed_changes,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
    return raw


def consume_confirmation(
    *, raw: str, actor: User, target: User, actions: list[str],
    proposed_changes: dict[str, object],
) -> ChangeConfirmation:
    confirmation = ChangeConfirmation.objects.select_for_update().filter(token_digest=token_digest(raw)).first()
    if not confirmation or confirmation.consumed_at or confirmation.expires_at <= timezone.now():
        raise ValueError("CONFIRMATION_INVALID")
    if confirmation.actor_uuid != actor.uuid or confirmation.target_uuid != target.uuid or confirmation.target_version != target.version:
        raise ValueError("CONFIRMATION_MISMATCH")
    if confirmation.actions != sorted(actions) or confirmation.proposed_changes != proposed_changes:
        raise ValueError("CONFIRMATION_MISMATCH")
    if confirmation.actor_auth_version != actor.auth_version or confirmation.session_epoch != current_epoch():
        raise ValueError("CONFIRMATION_INVALID")
    confirmation.consumed_at = timezone.now()
    confirmation.save(update_fields=["consumed_at"])
    return confirmation


def update_user(
    *, actor: User, target: User, version: int, display_name: str | None = None,
    role: str | None = None, active: bool | None = None, confirmation: str | None = None,
    idempotency_key: str | None = None, request_payload: dict[str, object] | None = None,
) -> User:
    with transaction.atomic():
        target = User.objects.select_for_update().get(pk=target.pk)
        if version != target.version:
            raise ValueError("STALE_VERSION")
        if role is not None and role not in User.Role.values:
            raise ValueError("ROLE_INVALID")
        actions = [x for x in ("disable" if active is False and target.active else None, "change_role" if role is not None and role != target.role else None) if x]
        proposed = {k: v for k, v in (("role", role), ("active", active)) if v is not None and (k == "active" and v != target.active or k == "role" and v != target.role)}
        used_confirmation = None
        if actions:
            if not confirmation:
                raise ValueError("CONFIRMATION_REQUIRED")
            used_confirmation = consume_confirmation(
                raw=confirmation,
                actor=actor,
                target=target,
                actions=actions,
                proposed_changes=dict(proposed),
            )
        old_display_name, old_role, old_active = target.display_name, target.role, target.active
        if display_name is not None:
            display_name = display_name.strip()
            if not 1 <= len(display_name) <= 128:
                raise ValueError("DISPLAY_NAME_INVALID")
        if role is not None:
            if target.role == User.Role.ADMIN and role != User.Role.ADMIN and target.active and User.objects.filter(role=User.Role.ADMIN, active=True).count() <= 1:
                raise ValueError("LAST_ADMIN_PROTECTED")
        if active is not None:
            if target.role == User.Role.ADMIN and target.active and not active and User.objects.filter(role=User.Role.ADMIN, active=True).count() <= 1:
                raise ValueError("LAST_ADMIN_PROTECTED")
        changed_display = display_name is not None and old_display_name != display_name
        changed_role = role is not None and old_role != role
        changed_active = active is not None and old_active != active
        if not (changed_display or changed_role or changed_active):
            return target
        if display_name is not None:
            target.display_name = display_name
        if role is not None:
            target.role = role
        if active is not None:
            target.active = active
        target.version += 1
        if changed_role or changed_active:
            target.auth_version += 1
        target.save(update_fields=["display_name", "role", "active", "version", "auth_version"])
        operation_uuid = uuid.uuid4()
        if changed_display:
            _record_event(category="account", action="user_updated", result="success", actor_uuid=actor.uuid, operation_uuid=operation_uuid, before={"display_name": old_display_name}, after={"display_name": display_name}, summary={"changed": True})
        if changed_role:
            _record_event(category="account", action="role_changed", result="success", actor_uuid=actor.uuid, operation_uuid=operation_uuid, summary={"changed": True})
        if changed_active and active is False:
            _record_event(category="account", action="user_disabled", result="success", actor_uuid=actor.uuid, operation_uuid=operation_uuid, summary={"changed": True})
        elif changed_active:
            _record_event(category="account", action="user_updated", result="success", actor_uuid=actor.uuid, operation_uuid=operation_uuid, summary={"changed": True})
        if idempotency_key and request_payload is not None:
            save_receipt(
                actor_uuid=actor.uuid, idempotency_key=idempotency_key,
                payload=request_payload, operation_uuid=operation_uuid,
                confirmation_uuid=used_confirmation.uuid if used_confirmation else None,
                result_ref=_public_user_payload(target),
                allowed_keys=UPDATE_RECEIPT_KEYS,
            )
        return target


def reset_user_password(
    *, actor: User, target: User, version: int, new_password: str, confirmation: str,
    idempotency_key: str | None = None, request_payload: dict[str, object] | None = None,
) -> User:
    if actor.uuid == target.uuid:
        raise ValueError("RESET_SELF_NOT_ALLOWED")
    validate_password(new_password)
    password_hash = hash_password(new_password)
    with transaction.atomic():
        target = User.objects.select_for_update().get(pk=target.pk)
        if target.version != version:
            raise ValueError("STALE_VERSION")
        used_confirmation = consume_confirmation(raw=confirmation, actor=actor, target=target, actions=["reset_password"], proposed_changes={})
        target.password_hash = password_hash
        target.must_change_password = True
        target.version += 1
        target.auth_version += 1
        target.save(update_fields=["password_hash", "must_change_password", "version", "auth_version"])
        operation_uuid = uuid.uuid4()
        _record_event(category="account", action="password_reset", result="success", actor_uuid=actor.uuid, operation_uuid=operation_uuid, summary={"changed": True})
        if idempotency_key and request_payload is not None:
            save_receipt(
                actor_uuid=actor.uuid, idempotency_key=idempotency_key,
                payload=request_payload, operation_uuid=operation_uuid,
                confirmation_uuid=used_confirmation.uuid,
                result_ref=_public_user_payload(target),
                allowed_keys=RESET_RECEIPT_KEYS,
            )
        return target
