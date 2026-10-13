import uuid

import pytest
from accounts.models import User
from accounts.passwords import hash_password
from assets.models import Asset, AssetIdentity
from audit.models import AuditEvent
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


def physical_payload(asset_no: str = "PHY-001", *, status: str = "active", **overrides):
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
        "purchase_date": "2026-01-01",
        "rack_date": "2026-01-02",
        "warranty_end": "",
        "expires_on": "",
        "credential_ref": "",
        "host_asset_no": "",
        "internal_ips": [],
        "external_ips": [],
    }
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
def test_asset_create_validates_required_type_fields_and_audit_secret_boundary(control_state):
    client = logged_client("admin")
    response = post_asset(
        client,
        physical_payload(
            credential_ref="vault://asset/secret",
            internal_ips=["10.0.0.2"],
        ),
    )
    assert response.status_code == 201
    asset = Asset.objects.get()
    assert asset.identity.normalized_asset_no == "phy-001"
    event = AuditEvent.objects.get(category="asset", action="created", result="success")
    assert event.before is None
    assert event.after["serial"] == "SN-PHY-001"
    assert "credential_ref" not in str(event.before)
    assert "credential_ref" not in str(event.after)
    assert "vault://asset/secret" not in str(event.summary)

    missing_serial = post_asset(client, physical_payload("PHY-002", serial=""))
    nonvirtual_host = post_asset(client, physical_payload("PHY-003", host_asset_no="PHY-001"))
    assert missing_serial.status_code == 422
    assert missing_serial.json()["code"] == "SERIAL_REQUIRED"
    assert nonvirtual_host.status_code == 422
    assert nonvirtual_host.json()["code"] == "HOST_NOT_APPLICABLE"


@pytest.mark.django_db(databases={"default", "control"})
def test_asset_number_is_permanent_but_released_identifiers_can_be_reused(control_state):
    client = logged_client("admin")
    first = post_asset(client, physical_payload("PHY-010", serial="SERIAL-REUSE", hostname="reuse.example.local"))
    assert first.status_code == 201
    asset_id = first.json()["id"]
    duplicate = post_asset(client, physical_payload(" phy-010 ", serial="SERIAL-OTHER", hostname="other.example.local"))
    assert duplicate.status_code == 409
    preview = client.post(f"/api/v1/assets/{asset_id}/delete-preview", {}, content_type="application/json")
    assert preview.status_code == 200
    deleted = client.delete(
        f"/api/v1/assets/{asset_id}",
        {"confirmation_id": preview.json()["confirmation_id"]},
        content_type="application/json",
        headers={"If-Match": "1", "Idempotency-Key": "delete-phy-010"},
    )
    assert deleted.status_code == 204
    assert Asset.objects.count() == 0
    assert AssetIdentity.objects.get(normalized_asset_no="phy-010").last_deleted_at is not None

    reused_number = post_asset(client, physical_payload("PHY-010", serial="SERIAL-NEW", hostname="new.example.local"))
    reused_identifiers = post_asset(
        client,
        physical_payload("PHY-011", serial="SERIAL-REUSE", hostname="reuse.example.local"),
    )
    assert reused_number.status_code == 409
    assert reused_number.json()["code"] == "ASSET_NO_CONFLICT"
    assert reused_identifiers.status_code == 201


@pytest.mark.django_db(databases={"default", "control"})
@pytest.mark.parametrize("status", ["planned", "purchased", "racked", "active", "repair", "retired"])
def test_admin_and_editor_can_create_all_initial_statuses_but_viewer_cannot(control_state, status):
    editor = logged_client("editor", f"editor-{status}")
    assert post_asset(editor, physical_payload(f"ED-{status}", status=status)).status_code == 201

    viewer = logged_client("viewer", f"viewer-{status}")
    denied = post_asset(viewer, physical_payload(f"VW-{status}", status=status))
    assert denied.status_code == 403


@pytest.mark.django_db(databases={"default", "control"})
def test_editor_status_transitions_follow_matrix_and_unchanged_status_can_edit(control_state):
    client = logged_client("editor")
    created = post_asset(client, physical_payload("PHY-020", status="planned"))
    assert created.status_code == 201
    asset_id = created.json()["id"]
    allowed = client.patch(
        f"/api/v1/assets/{asset_id}",
        {**physical_payload("PHY-020", status="purchased"), "name": "采购完成"},
        content_type="application/json",
        headers={"If-Match": "1", "Idempotency-Key": "asset-status-purchased"},
    )
    denied = client.patch(
        f"/api/v1/assets/{asset_id}",
        {**physical_payload("PHY-020", status="retired"), "name": "直接退役"},
        content_type="application/json",
        headers={"If-Match": "2", "Idempotency-Key": "asset-status-retired"},
    )
    unchanged = client.patch(
        f"/api/v1/assets/{asset_id}",
        {"version": 2, "name": "仅改名称"},
        content_type="application/json",
        headers={"Idempotency-Key": "asset-same-status"},
    )
    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert unchanged.status_code == 200


@pytest.mark.django_db(databases={"default", "control"})
def test_ip_normalization_rejects_equivalent_duplicates_and_zone_ids(control_state):
    client = logged_client("admin")
    first = post_asset(client, physical_payload("PHY-030", internal_ips=["::ffff:192.0.2.10"]))
    assert first.status_code == 201
    duplicate_ip = post_asset(client, physical_payload("PHY-031", internal_ips=["192.0.2.10"]))
    zone_id = post_asset(client, physical_payload("PHY-032", internal_ips=["fe80::1%eth0"]))
    assert duplicate_ip.status_code == 409
    assert duplicate_ip.json()["code"] == "IP_CONFLICT"
    assert zone_id.status_code == 422
    assert zone_id.json()["code"] == "IP_INVALID"
