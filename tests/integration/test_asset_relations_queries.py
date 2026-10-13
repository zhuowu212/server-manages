import uuid

import pytest
from accounts.models import User
from accounts.passwords import hash_password
from assets.models import Asset
from django.test import Client

PASSWORD = "安全密码安全密码123456"


def make_user(role: str, username: str) -> User:
    return User.objects.create(
        username=username,
        username_key=username,
        display_name=username,
        role=role,
        password_hash=hash_password(PASSWORD),
        must_change_password=False,
    )


def logged_client(role: str = "admin", username: str | None = None) -> Client:
    username = username or role
    make_user(role, username)
    client = Client()
    assert client.post(
        "/api/v1/auth/login",
        {"username": username, "password": PASSWORD},
        content_type="application/json",
    ).status_code == 200
    return client


def physical_payload(asset_no: str, *, status: str = "active", **overrides):
    payload = {
        "name": f"物理机 {asset_no}",
        "asset_no": asset_no,
        "type": "physical",
        "purpose": "业务",
        "environment": "生产",
        "owner": "运维",
        "status": status,
        "room": "A机房",
        "region": "华东",
        "hardware_text": "",
        "serial": f"SN-{asset_no}",
        "hostname": f"{asset_no.lower()}.example.local",
        "supplier": "",
        "purchase_date": "",
        "rack_date": "",
        "warranty_end": "",
        "expires_on": "",
        "credential_ref": "",
        "host_asset_no": "",
        "internal_ips": [],
        "external_ips": [],
    }
    payload.update(overrides)
    return payload


def virtual_payload(asset_no: str, host_asset_no: str, **overrides):
    payload = physical_payload(
        asset_no,
        type="virtual",
        serial="",
        hostname=f"{asset_no.lower()}.vm.local",
        host_asset_no=host_asset_no,
    )
    payload.update(overrides)
    return payload


def post_asset(client: Client, payload: dict[str, object], key: str | None = None):
    return client.post(
        "/api/v1/assets",
        payload,
        content_type="application/json",
        headers={"Idempotency-Key": key or f"asset-{uuid.uuid4()}"},
    )


@pytest.mark.django_db(databases={"default", "control"})
@pytest.mark.parametrize("status", ["racked", "active", "repair"])
def test_virtual_machine_can_use_only_valid_physical_host_statuses(control_state, status):
    client = logged_client("admin", f"admin-{status}")
    assert post_asset(client, physical_payload(f"HOST-{status}", status=status)).status_code == 201
    vm = post_asset(client, virtual_payload(f"VM-{status}", f"HOST-{status}"))
    assert vm.status_code == 201


@pytest.mark.django_db(databases={"default", "control"})
def test_virtual_machine_rejects_invalid_or_missing_hosts(control_state):
    client = logged_client("admin")
    assert post_asset(client, physical_payload("HOST-PLANNED", status="planned")).status_code == 201
    planned = post_asset(client, virtual_payload("VM-PLANNED", "HOST-PLANNED"))
    missing = post_asset(client, virtual_payload("VM-MISSING", "NO-SUCH-HOST"))
    assert planned.status_code == 409
    assert planned.json()["code"] == "INVALID_HOST"
    assert missing.status_code == 409
    assert missing.json()["code"] == "INVALID_HOST"


@pytest.mark.django_db(databases={"default", "control"})
def test_host_delete_and_invalid_status_change_are_blocked_by_virtual_children(control_state):
    client = logged_client("admin")
    host = post_asset(client, physical_payload("HOST-001", status="active"))
    assert host.status_code == 201
    vm = post_asset(client, virtual_payload("VM-001", "HOST-001"))
    assert vm.status_code == 201
    host_id = host.json()["id"]
    preview = client.post(f"/api/v1/assets/{host_id}/delete-preview", {}, content_type="application/json")
    assert preview.status_code == 409
    assert preview.json()["code"] == "DEPENDENCY_CONFLICT"
    retired = client.patch(
        f"/api/v1/assets/{host_id}",
        {"version": 1, "status": "retired"},
        content_type="application/json",
        headers={"Idempotency-Key": "retire-host-with-child"},
    )
    assert retired.status_code == 409
    assert retired.json()["code"] == "DEPENDENCY_CONFLICT"


@pytest.mark.django_db(databases={"default", "control"})
def test_virtual_machine_migration_uses_version_and_keeps_single_host(control_state):
    client = logged_client("admin")
    first_host = post_asset(client, physical_payload("HOST-A", status="active"))
    second_host = post_asset(client, physical_payload("HOST-B", status="active"))
    assert first_host.status_code == 201
    assert second_host.status_code == 201
    vm = post_asset(client, virtual_payload("VM-MOVE", "HOST-A"))
    assert vm.status_code == 201
    vm_id = vm.json()["id"]
    moved = client.patch(
        f"/api/v1/assets/{vm_id}",
        {"version": 1, "host_asset_no": "HOST-B"},
        content_type="application/json",
        headers={"Idempotency-Key": "move-vm"},
    )
    stale = client.patch(
        f"/api/v1/assets/{vm_id}",
        {"version": 1, "host_asset_no": "HOST-A"},
        content_type="application/json",
        headers={"Idempotency-Key": "move-vm-stale"},
    )
    assert moved.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"
    asset = Asset.objects.get(uuid=vm_id)
    assert asset.host.identity.normalized_asset_no == "host-b"


@pytest.mark.django_db(databases={"default", "control"})
def test_asset_search_filter_sort_and_pagination_are_stable(control_state):
    client = logged_client("viewer")
    admin = logged_client("admin")
    assert post_asset(admin, physical_payload("PHY-100", environment="生产", region="华东", owner="甲", internal_ips=["10.1.0.5"])).status_code == 201
    assert post_asset(admin, physical_payload("PHY-101", environment="测试", region="华北", owner="乙", internal_ips=["10.1.0.6"])).status_code == 201
    response = client.get("/api/v1/assets", {"q": "10.1.0.5", "environment": "生产", "sort": "asset_no", "page": "1", "page_size": "1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["asset_no"] == "PHY-100"
    assert payload["items"][0]["version"] == 1


@pytest.mark.django_db(databases={"default", "control"})
def test_delete_requires_admin_confirmation_and_replays_idempotently(control_state):
    editor = logged_client("editor")
    admin = logged_client("admin")
    created = post_asset(admin, physical_payload("PHY-DEL"))
    assert created.status_code == 201
    asset_id = created.json()["id"]
    editor_preview = editor.post(f"/api/v1/assets/{asset_id}/delete-preview", {}, content_type="application/json")
    assert editor_preview.status_code == 403
    preview = admin.post(f"/api/v1/assets/{asset_id}/delete-preview", {}, content_type="application/json")
    assert preview.status_code == 200
    first = admin.delete(
        f"/api/v1/assets/{asset_id}",
        {"confirmation_id": preview.json()["confirmation_id"]},
        content_type="application/json",
        headers={"If-Match": "1", "Idempotency-Key": "delete-replay"},
    )
    replay = admin.delete(
        f"/api/v1/assets/{asset_id}",
        {"confirmation_id": preview.json()["confirmation_id"]},
        content_type="application/json",
        headers={"If-Match": "1", "Idempotency-Key": "delete-replay"},
    )
    assert first.status_code == 204
    assert replay.status_code == 204
    assert replay["Idempotency-Replayed"] == "true"
