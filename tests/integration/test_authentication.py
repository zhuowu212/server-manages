from contextlib import contextmanager

import pytest
from accounts.models import User
from accounts.passwords import hash_password
from accounts.services import authenticate_local, change_password
from django.test import Client


@pytest.mark.django_db(databases={"default", "control"})
def test_password_is_argon2_and_unknown_login_is_generic(control_state):
    user = User.objects.create(
        username="admin", username_key="admin", display_name="管理员", role="admin",
        password_hash=hash_password("安全密码安全密码123456"), must_change_password=False,
    )
    assert user.password_hash.startswith("$argon2id$")
    assert "安全密码安全密码123456" not in user.password_hash
    response = Client().post("/api/v1/auth/login", {"username": "missing", "password": "错误密码123456"}, content_type="application/json")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.django_db(databases={"default", "control"})
def test_admin_can_create_user_with_required_fields(control_state):
    User.objects.create(username="admin", username_key="admin", display_name="管理员", role="admin", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    response = client.post(
        "/api/v1/users",
        {"username": "editor", "display_name": "编辑者", "role": "editor", "initial_password": "初始安全密码123456"},
        content_type="application/json",
        headers={"Idempotency-Key": "create-editor"},
    )
    assert response.status_code == 201
    created = User.objects.get(username_key="editor")
    assert created.must_change_password is True
    assert created.password_hash.startswith("$argon2id$")


@pytest.mark.django_db(databases={"default", "control"})
def test_account_create_rejects_length_edges_and_missing_role_without_partial_user(control_state):
    User.objects.create(username="admin", username_key="admin", display_name="管理员", role="admin", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    valid_12 = client.post(
        "/api/v1/users",
        {"username": "edge12", "display_name": "十二位", "role": "editor", "initial_password": "123456789012"},
        content_type="application/json",
        headers={"Idempotency-Key": "create-edge-12"},
    )
    missing_role = client.post(
        "/api/v1/users",
        {"username": "missing-role", "display_name": "缺角色", "initial_password": "123456789012"},
        content_type="application/json",
        headers={"Idempotency-Key": "create-missing-role"},
    )
    short_password = client.post(
        "/api/v1/users",
        {"username": "short-password", "display_name": "短密码", "role": "editor", "initial_password": "12345678901"},
        content_type="application/json",
        headers={"Idempotency-Key": "create-short-password"},
    )
    long_username = client.post(
        "/api/v1/users",
        {"username": "u" * 129, "display_name": "用户名过长", "role": "editor", "initial_password": "123456789012"},
        content_type="application/json",
        headers={"Idempotency-Key": "create-long-username"},
    )
    assert valid_12.status_code == 201
    assert missing_role.status_code == 422
    assert short_password.status_code == 422
    assert long_username.status_code == 422
    assert User.objects.filter(username_key__in=["missing-role", "short-password"]).count() == 0


@pytest.mark.django_db(databases={"default", "control"})
def test_viewer_cannot_create_user_server_side(control_state):
    from audit.models import AuditEvent

    User.objects.create(username="viewer", username_key="viewer", display_name="只读", role="viewer", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "viewer", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    response = client.post("/api/v1/users", {}, content_type="application/json")
    assert response.status_code == 403
    denied = AuditEvent.objects.get(category="security", action="authorization_denied")
    assert denied.result == "denied"
    assert denied.summary == {"target_kind": "users", "changed": False}


@pytest.mark.django_db(databases={"default", "control"})
def test_authorization_denied_audit_failure_is_safe(control_state, monkeypatch):
    import common.authorization as authorization

    User.objects.create(username="viewer", username_key="viewer", display_name="只读", role="viewer", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(authorization, "record_event", fail_audit)
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "viewer", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    response = client.post("/api/v1/users", {}, content_type="application/json")
    assert response.status_code == 503
    assert response.json()["code"] == "AUDIT_UNAVAILABLE"


@pytest.mark.django_db(databases={"default", "control"})
def test_five_failures_pause_even_correct_password(control_state):
    User.objects.create(username="admin", username_key="admin", display_name="管理员", role="admin", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)
    client = Client()
    for _ in range(5):
        response = client.post("/api/v1/auth/login", {"username": "admin", "password": "错误密码错误密码1234"}, content_type="application/json")
    assert response.status_code == 429
    response = client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json")
    assert response.status_code == 429
    assert response.json()["code"] == "THROTTLED"
    assert response["Retry-After"] == "900"


@pytest.mark.django_db(databases={"default", "control"})
def test_login_pause_expires_after_fifteen_minutes(control_state, clock):
    User.objects.create(username="admin", username_key="admin", display_name="管理员", role="admin", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)
    client = Client()
    for _ in range(5):
        response = client.post("/api/v1/auth/login", {"username": "admin", "password": "错误密码错误密码1234"}, content_type="application/json")
    assert response.status_code == 429
    clock.shift(15 * 60 + 1)
    response = client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json")
    assert response.status_code == 200


@pytest.mark.django_db(databases={"default", "control"})
def test_first_login_must_change_password_before_business_routes(control_state):
    User.objects.create(username="admin", username_key="admin", display_name="管理员", role="admin", password_hash=hash_password("安全密码安全密码123456"), must_change_password=True)
    client = Client()
    assert client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json").status_code == 200
    blocked = client.get("/api/v1/users")
    allowed = client.post(
        "/api/v1/auth/password",
        {"current_password": "安全密码安全密码123456", "new_password": "新安全密码新安全密码123456"},
        content_type="application/json",
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert allowed.status_code == 204


@pytest.mark.django_db(databases={"default", "control"})
def test_csrf_is_required_for_cookie_auth_writes(control_state):
    client = Client(enforce_csrf_checks=True)
    response = client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json")
    assert response.status_code == 403


@pytest.mark.django_db(databases={"default", "control"})
def test_password_change_requires_current_password_and_uses_secure_session_cookie(control_state):
    User.objects.create(username="admin", username_key="admin", display_name="管理员", role="admin", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)
    client = Client()
    response = client.post("/api/v1/auth/login", {"username": "admin", "password": "安全密码安全密码123456"}, content_type="application/json")
    assert response.status_code == 200
    assert "Secure" in response.cookies["sessionid"].output()
    response = client.post("/api/v1/auth/password", {"current_password": "错误密码错误密码1234", "new_password": "新安全密码新安全密码123456"}, content_type="application/json")
    assert response.status_code == 422


@pytest.mark.django_db(databases={"default", "control"})
def test_password_verification_and_hashing_stay_outside_transactions(control_state, monkeypatch):
    import accounts.services as services

    user = User.objects.create(
        username="admin",
        username_key="admin",
        display_name="管理员",
        role="admin",
        password_hash=hash_password("安全密码安全密码123456"),
        must_change_password=False,
    )
    verify_states: list[bool] = []
    hash_states: list[bool] = []
    in_service_write: list[bool] = [False]
    real_verify = services.verify_password_equalized
    real_hash = services.hash_password
    real_atomic = services.transaction.atomic

    def observed_verify(*args, **kwargs):
        verify_states.append(in_service_write[0])
        return real_verify(*args, **kwargs)

    def observed_hash(*args, **kwargs):
        hash_states.append(in_service_write[0])
        return real_hash(*args, **kwargs)

    @contextmanager
    def observed_atomic(*args, **kwargs):
        with real_atomic(*args, **kwargs):
            in_service_write[0] = True
            try:
                yield
            finally:
                in_service_write[0] = False

    monkeypatch.setattr(services, "verify_password_equalized", observed_verify)
    monkeypatch.setattr(services, "hash_password", observed_hash)
    monkeypatch.setattr(services.transaction, "atomic", observed_atomic)
    authenticated, throttled = authenticate_local("admin", "安全密码安全密码123456")
    assert authenticated is not None and not throttled
    change_password(user, "安全密码安全密码123456", "新的安全密码123456")
    assert verify_states and not any(verify_states)
    assert hash_states and not any(hash_states)


@pytest.mark.django_db(databases={"default", "control"})
def test_account_create_idempotency_excludes_secret_but_rejects_non_secret_reuse(control_state):
    User.objects.create(
        username="admin",
        username_key="admin",
        display_name="管理员",
        role="admin",
        password_hash=hash_password("安全密码安全密码123456"),
        must_change_password=False,
    )
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    payload = {
        "username": "editor",
        "display_name": "编辑者",
        "role": "editor",
        "initial_password": "初始安全密码123456",
    }
    first = client.post(
        "/api/v1/users", payload, content_type="application/json",
        headers={"Idempotency-Key": "create-idempotent"},
    )
    replay = client.post(
        "/api/v1/users",
        {**payload, "initial_password": "另一组安全密码123456"},
        content_type="application/json",
        headers={"Idempotency-Key": "create-idempotent"},
    )
    conflict = client.post(
        "/api/v1/users",
        {**payload, "display_name": "不同名称"},
        content_type="application/json",
        headers={"Idempotency-Key": "create-idempotent"},
    )
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert User.objects.filter(username_key="editor").count() == 1


@pytest.mark.django_db(databases={"default", "control"})
def test_account_create_audit_failure_rolls_back_user_and_receipt(control_state, monkeypatch):
    import accounts.services as services
    from common.models import OperationReceipt

    User.objects.create(
        username="admin",
        username_key="admin",
        display_name="管理员",
        role="admin",
        password_hash=hash_password("安全密码安全密码123456"),
        must_change_password=False,
    )

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(services, "record_event", fail_audit)
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": "admin", "password": "安全密码安全密码123456"},
        content_type="application/json",
    ).status_code == 200
    response = client.post(
        "/api/v1/users",
        {
            "username": "editor",
            "display_name": "编辑者",
            "role": "editor",
            "initial_password": "初始安全密码123456",
        },
        content_type="application/json",
        headers={"Idempotency-Key": "create-audit-failure"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "AUDIT_UNAVAILABLE"
    assert User.objects.filter(username_key="editor").count() == 0
    assert OperationReceipt.objects.count() == 0


@pytest.mark.django_db(databases={"default", "control"})
def test_error_payload_is_structured_and_safe(control_state):
    response = Client().post("/api/v1/auth/login", b"{", content_type="application/json")
    payload = response.json()
    assert response.status_code == 422
    assert payload["code"] == "INVALID_JSON"
    assert isinstance(payload["message"], str) and payload["message"]
    assert payload["field_errors"] == []
    assert payload["request_id"]


@pytest.mark.django_db(databases={"default", "control"})
def test_password_reset_revokes_existing_sessions(control_state):
    from accounts.services import create_confirmation, reset_user_password

    admin = User.objects.create(username="admin", username_key="admin", display_name="管理员", role="admin", password_hash=hash_password("安全密码安全密码123456"), must_change_password=False)
    editor = User.objects.create(username="editor", username_key="editor", display_name="编辑", role="editor", password_hash=hash_password("编辑安全密码123456"), must_change_password=False)
    editor_client = Client()
    assert editor_client.post("/api/v1/auth/login", {"username": "editor", "password": "编辑安全密码123456"}, content_type="application/json").status_code == 200
    confirmation = create_confirmation(actor=admin, target=editor, actions=["reset_password"], proposed_changes={})
    reset_user_password(
        actor=admin,
        target=editor,
        version=editor.version,
        new_password="重置后的安全密码123456",
        confirmation=confirmation,
    )
    response = editor_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] in {"SESSION_INVALID", "UNAUTHENTICATED"}
