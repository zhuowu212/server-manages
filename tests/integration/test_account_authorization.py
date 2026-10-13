import pytest
from accounts.models import User
from accounts.passwords import hash_password
from common.models import ChangeConfirmation, OperationReceipt
from django.test import Client


def make_user(role, username):
    return User.objects.create(
        username=username, username_key=username, display_name=username, role=role,
        password_hash=hash_password("安全密码安全密码123456"), must_change_password=False,
    )


@pytest.mark.django_db(databases={"default", "control"})
def test_username_is_immutable_and_display_name_can_change(control_state):
    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    response = client.patch(
        f"/api/v1/users/{target.uuid}",
        {"version": 1, "username": "changed", "display_name": "新名称"},
        content_type="application/json",
        headers={"Idempotency-Key": "immutable-username"},
    )
    assert response.status_code == 422
    response = client.patch(
        f"/api/v1/users/{target.uuid}",
        {"version": 1, "display_name": "新名称"},
        content_type="application/json",
        headers={"Idempotency-Key": "display-name"},
    )
    assert response.status_code == 200
    target.refresh_from_db()
    assert target.username == "editor" and target.display_name == "新名称"


@pytest.mark.django_db(databases={"default", "control"})
def test_non_admin_account_routes_are_server_side_denied_and_audited(control_state):
    from audit.models import AuditEvent

    make_user("editor", "editor")
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "editor", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    response = client.get("/api/v1/users")
    assert response.status_code == 403
    event = AuditEvent.objects.get(category="security", action="authorization_denied")
    assert event.result == "denied"
    assert event.before is None
    assert event.after is None
    assert event.summary == {"target_kind": "users", "changed": False}
    assert "password" not in str(event.summary).casefold()


@pytest.mark.django_db(databases={"default", "control"})
def test_sensitive_account_change_requires_bound_confirmation(control_state):
    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    response = client.patch(
        f"/api/v1/users/{target.uuid}",
        {"version": 1, "active": False},
        content_type="application/json",
        headers={"Idempotency-Key": "disable-without-confirmation"},
    )
    assert response.status_code == 422
    preview = client.post(f"/api/v1/users/{target.uuid}/change-preview", {"actions": ["disable"], "changes": {"active": False}}, content_type="application/json")
    assert preview.status_code == 200
    confirmation = preview.json()["confirmation_id"]
    response = client.patch(
        f"/api/v1/users/{target.uuid}",
        {"version": 1, "active": False, "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "disable-editor"},
    )
    assert response.status_code == 200
    target.refresh_from_db()
    assert target.active is False


@pytest.mark.django_db(databases={"default", "control"})
def test_last_admin_cannot_be_disabled(control_state):
    admin = make_user("admin", "admin")
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    preview = client.post(f"/api/v1/users/{admin.uuid}/change-preview", {"actions": ["disable"], "changes": {"active": False}}, content_type="application/json")
    response = client.patch(
        f"/api/v1/users/{admin.uuid}",
        {"version": 1, "active": False, "confirmation_id": preview.json()["confirmation_id"]},
        content_type="application/json",
        headers={"Idempotency-Key": "disable-admin"},
    )
    assert response.status_code == 409


@pytest.mark.django_db(databases={"default", "control"})
def test_reset_password_never_puts_secret_in_confirmation(control_state):
    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    preview = client.post(f"/api/v1/users/{target.uuid}/change-preview", {"actions": ["reset_password"], "changes": {}}, content_type="application/json")
    confirmation = preview.json()["confirmation_id"]
    response = client.post(
        f"/api/v1/users/{target.uuid}/reset-password",
        {"version": 1, "new_password": "全新安全密码123456", "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "reset-editor"},
    )
    assert response.status_code == 200
    assert "全新安全密码123456" not in str(response.content)


@pytest.mark.django_db(databases={"default", "control"})
def test_confirmation_preview_requires_exact_actions_and_proposed_values(control_state):
    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    invalid_disable = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["disable"], "changes": {"active": True}},
        content_type="application/json",
    )
    invalid_role = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["change_role"], "changes": {"role": "editor"}},
        content_type="application/json",
    )
    mixed_reset = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["reset_password", "disable"], "changes": {"active": False}},
        content_type="application/json",
    )
    valid = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["disable", "change_role"], "changes": {"active": False, "role": "viewer"}},
        content_type="application/json",
    )
    assert invalid_disable.status_code == 422
    assert invalid_role.status_code == 422
    assert mixed_reset.status_code == 422
    assert valid.status_code == 200


@pytest.mark.django_db(databases={"default", "control"})
def test_confirmation_consumption_and_receipt_are_atomic_on_audit_failure(control_state, monkeypatch):
    import accounts.services as services

    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    preview = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["disable"], "changes": {"active": False}},
        content_type="application/json",
    )
    confirmation = preview.json()["confirmation_id"]

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(services, "record_event", fail_audit)
    response = client.patch(
        f"/api/v1/users/{target.uuid}",
        {"version": 1, "active": False, "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "disable-atomic"},
    )
    target.refresh_from_db()
    confirmation_row = ChangeConfirmation.objects.get()
    assert response.status_code == 503
    assert response.json()["code"] == "AUDIT_UNAVAILABLE"
    assert target.active is True
    assert confirmation_row.consumed_at is None
    assert OperationReceipt.objects.count() == 0


@pytest.mark.django_db(databases={"default", "control"})
def test_mixed_account_update_events_share_operation_and_receipt_confirmation(control_state):
    from audit.models import AuditEvent

    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    preview = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["disable", "change_role"], "changes": {"active": False, "role": "viewer"}},
        content_type="application/json",
    )
    confirmation = preview.json()["confirmation_id"]
    response = client.patch(
        f"/api/v1/users/{target.uuid}",
        {
            "version": 1,
            "display_name": "新显示名",
            "role": "viewer",
            "active": False,
            "confirmation_id": confirmation,
        },
        content_type="application/json",
        headers={"Idempotency-Key": "mixed-account-update"},
    )
    assert response.status_code == 200
    events = list(AuditEvent.objects.filter(category="account").order_by("action"))
    assert {event.action for event in events} == {"role_changed", "user_disabled", "user_updated"}
    operation_ids = {event.operation_uuid for event in events}
    assert len(operation_ids) == 1
    confirmation_row = ChangeConfirmation.objects.get()
    receipt = OperationReceipt.objects.get(idempotency_key="mixed-account-update")
    assert receipt.operation_uuid == operation_ids.pop()
    assert receipt.confirmation_uuid == confirmation_row.uuid
    assert confirmation_row.consumed_at is not None


@pytest.mark.django_db(databases={"default", "control"})
def test_expired_confirmation_rejects_without_partial_change(control_state):
    from datetime import timedelta

    from django.utils import timezone

    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    preview = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["change_role"], "changes": {"role": "viewer"}},
        content_type="application/json",
    )
    confirmation = preview.json()["confirmation_id"]
    ChangeConfirmation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    response = client.patch(
        f"/api/v1/users/{target.uuid}",
        {"version": 1, "role": "viewer", "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "expired-confirmation"},
    )
    target.refresh_from_db()
    assert response.status_code == 409
    assert target.role == "editor"
    assert ChangeConfirmation.objects.get().consumed_at is None
    assert OperationReceipt.objects.count() == 0


@pytest.mark.django_db(databases={"default", "control"})
def test_password_reset_replay_returns_original_without_reusing_secret_or_confirmation(control_state):
    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    preview = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["reset_password"], "changes": {}},
        content_type="application/json",
    )
    confirmation = preview.json()["confirmation_id"]
    first = client.post(
        f"/api/v1/users/{target.uuid}/reset-password",
        {"version": 1, "new_password": "第一组安全密码123456", "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "reset-replay"},
    )
    replay = client.post(
        f"/api/v1/users/{target.uuid}/reset-password",
        {"version": 1, "new_password": "第二组安全密码123456", "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "reset-replay"},
    )
    new_key = client.post(
        f"/api/v1/users/{target.uuid}/reset-password",
        {"version": 1, "new_password": "第三组安全密码123456", "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "reset-new-key"},
    )
    target.refresh_from_db()
    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert new_key.status_code == 409
    assert new_key.json()["code"] == "STALE_VERSION"
    assert target.check_password("第一组安全密码123456")
    assert not target.check_password("第二组安全密码123456")


@pytest.mark.django_db(databases={"default", "control"})
def test_password_reset_receipt_stores_internal_confirmation_uuid_only(control_state):
    make_user("admin", "admin")
    target = make_user("editor", "editor")
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    preview = client.post(
        f"/api/v1/users/{target.uuid}/change-preview",
        {"actions": ["reset_password"], "changes": {}},
        content_type="application/json",
    )
    confirmation = preview.json()["confirmation_id"]
    response = client.post(
        f"/api/v1/users/{target.uuid}/reset-password",
        {"version": 1, "new_password": "新的安全密码123456", "confirmation_id": confirmation},
        content_type="application/json",
        headers={"Idempotency-Key": "reset-confirmation-ref"},
    )
    assert response.status_code == 200
    receipt = OperationReceipt.objects.get(idempotency_key="reset-confirmation-ref")
    confirmation_row = ChangeConfirmation.objects.get()
    assert receipt.confirmation_uuid == confirmation_row.uuid
    assert confirmation not in str(receipt.result_ref)
