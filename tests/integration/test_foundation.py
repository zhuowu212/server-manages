import sqlite3
import uuid

import pytest
from common.db import configure_connection, connection_pragmas, independent_work_unit
from common.logging import safe_fields
from django.conf import settings
from django.db import IntegrityError, connections, transaction
from django.db.utils import OperationalError


def test_sqlite_durability_pragmas(tmp_path):
    conn = sqlite3.connect(tmp_path / "foundation.sqlite")
    configure_connection(conn)
    values = connection_pragmas(conn)
    assert values == {
        "journal_mode": "wal",
        "synchronous": 2,
        "foreign_keys": 1,
        "busy_timeout": 5000,
        "wal_autocheckpoint": 1000,
    }


def test_sensitive_logging_is_positive_allowlist():
    fields = safe_fields({
        "request_id": "r1",
        "route_name": "accounts.login",
        "password": "do-not-log",
        "payload": {"token": "secret", "status": "hidden"},
    })
    assert fields == {"request_id": "r1", "route_name": "accounts.login"}


@pytest.mark.django_db
def test_system_setting_database_constraint_is_empty():
    from common.models import SystemSetting

    with pytest.raises(IntegrityError):
        SystemSetting.objects.create(key="unknown", typed_value="value")


def test_django_connection_is_not_persistent():
    assert connections["default"].settings_dict["CONN_MAX_AGE"] == 0


@pytest.mark.django_db(transaction=True)
def test_independent_work_unit_closes_connection():
    with independent_work_unit("default"):
        connections["default"].ensure_connection()
        assert connections["default"].connection is not None
    assert connections["default"].connection is None


def test_event_and_business_timezone_defaults():
    assert settings.USE_TZ is True
    assert settings.TIME_ZONE == "Asia/Shanghai"


def test_django_wrapped_busy_error_is_detected():
    from common.db import is_busy_error

    wrapped = OperationalError("database is locked")
    assert is_busy_error(wrapped)


@pytest.mark.django_db
def test_audit_events_are_immutable():
    from audit.models import AuditEvent

    event = AuditEvent.objects.create(category="asset", action="created", result="success", instance_id="00000000-0000-0000-0000-000000000001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AuditEvent.objects.filter(pk=event.pk).update(result="failed")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            event.delete()


@pytest.mark.django_db
def test_audit_login_rejected_is_not_a_valid_result():
    from audit.models import AuditEvent

    with pytest.raises(IntegrityError):
        AuditEvent.objects.create(
            category="authentication",
            action="login",
            result="rejected",
            instance_id="00000000-0000-0000-0000-000000000001",
        )


@pytest.mark.django_db
def test_audit_instance_id_is_stable_and_event_matrix_is_valid():
    from audit.services import record_event

    first = record_event(category="authentication", action="login", result="failed", summary={"changed": False})
    second = record_event(category="authentication", action="login", result="failed", summary={"changed": False})
    assert first.instance_id == second.instance_id
    with pytest.raises(ValueError, match="AUDIT_ENUM_INVALID"):
        record_event(category="authentication", action="login", result="rejected", summary={"changed": False})


@pytest.mark.django_db
def test_audit_service_rejects_secret_fields_and_conflicting_duplicate_events():
    from audit.services import record_event

    with pytest.raises(ValueError, match="AUDIT_SECRET_FIELD"):
        record_event(
            category="account",
            action="password_reset",
            result="success",
            summary={"password": "never"},
        )
    event_uuid = uuid.uuid4()
    first = record_event(
        event_uuid=event_uuid,
        category="authentication",
        action="login",
        result="failed",
        summary={"changed": False},
    )
    replay = record_event(
        event_uuid=event_uuid,
        category="authentication",
        action="login",
        result="failed",
        summary={"changed": False},
    )
    assert replay.pk == first.pk
    with pytest.raises(ValueError, match="AUDIT_EVENT_CONFLICT"):
        record_event(
            event_uuid=event_uuid,
            category="authentication",
            action="login",
            result="success",
            summary={"changed": True},
        )


@pytest.mark.django_db
def test_audit_event_matrix_is_enforced_by_service_and_database():
    from audit.models import AuditEvent
    from audit.services import EVENT_MATRIX, record_event

    expected = {
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
    assert EVENT_MATRIX == expected

    instance_id = uuid.UUID(int=1)
    for (category, action), results in expected.items():
        for result in results:
            record_event(category=category, action=action, result=result, summary={"changed": False})
            AuditEvent.objects.create(
                instance_id=instance_id,
                category=category,
                action=action,
                result=result,
            )

    invalid_combinations = [
        ("authentication", "login", "rejected"),
        ("backup", "deleted", "started"),
        ("security", "authorization_denied", "failed"),
        ("asset", "downloaded", "success"),
    ]
    for category, action, result in invalid_combinations:
        with pytest.raises(ValueError, match="AUDIT_ENUM_INVALID"):
            record_event(category=category, action=action, result=result, summary={"changed": False})
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AuditEvent.objects.create(
                    instance_id=instance_id,
                    category=category,
                    action=action,
                    result=result,
                )


@pytest.mark.django_db
def test_audit_allows_ordinary_values_and_rejects_secret_markers_anywhere():
    from audit.services import record_event

    event = record_event(
        category="asset",
        action="updated",
        result="success",
        before={"name": "旧名称", "internal_ips": ["10.0.0.1"], "owner": "运维"},
        after={"name": "新名称", "internal_ips": ["10.0.0.2"], "owner": "运维"},
        summary={"changed": True, "target_kind": "asset", "target_uuid": str(uuid.uuid4())},
    )
    assert event.before["name"] == "旧名称"
    assert event.after["internal_ips"] == ["10.0.0.2"]

    for payload in (
        {"password_hash": "never"},
        {"changed": True, "nested": {"token": "never"}},
        {"credential_ref": "vault://secret/path"},
        {"private_key": "never"},
    ):
        with pytest.raises(ValueError, match="AUDIT_"):
            record_event(
                category="account",
                action="user_updated",
                result="success",
                summary=payload,
            )
