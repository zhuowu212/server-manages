import pytest
from accounts.models import User
from accounts.passwords import hash_password
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


@pytest.mark.e2e
@pytest.mark.django_db(databases={"default", "control"})
def test_asset_pages_cover_create_list_and_detail(control_state):
    make_user("admin", "admin")
    client = Client()
    assert client.post("/login", {"username": "admin", "password": PASSWORD}).status_code == 302
    empty = client.get("/assets")
    assert empty.status_code == 200
    assert "新增资产" in empty.content.decode()
    form = client.get("/assets/new")
    assert form.status_code == 200
    assert "宿主机编号" in form.content.decode()
    created = client.post(
        "/assets/new",
        {
            "asset_no": "PHY-UI",
            "name": "界面资产",
            "type": "physical",
            "status": "active",
            "purpose": "业务",
            "environment": "生产",
            "owner": "运维",
            "room": "A机房",
            "region": "华东",
            "serial": "SN-UI",
            "hostname": "phy-ui.example.local",
            "internal_ips": "10.9.0.1",
        },
        follow=True,
    )
    content = created.content.decode()
    assert created.status_code == 200
    assert "PHY-UI" in content
    assert "界面资产" in content
    assert 'data-confirm-action="删除资产"' in content


@pytest.mark.e2e
@pytest.mark.django_db(databases={"default", "control"})
def test_asset_navigation_hides_write_controls_for_viewer_but_api_denies(control_state):
    make_user("viewer", "viewer")
    client = Client()
    assert client.post("/login", {"username": "viewer", "password": PASSWORD}).status_code == 302
    page = client.get("/assets")
    content = page.content.decode()
    assert page.status_code == 200
    assert "新增资产" not in content
    denied = client.post("/api/v1/assets", {}, content_type="application/json")
    assert denied.status_code == 403
