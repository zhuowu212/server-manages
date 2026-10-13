import pytest
from accounts.models import User
from accounts.passwords import hash_password
from django.test import Client


@pytest.mark.e2e
@pytest.mark.django_db(databases={"default", "control"})
def test_account_pages_render_chinese_labels_and_admin_navigation(control_state):
    User.objects.create(
        username="admin",
        username_key="admin",
        display_name="管理员",
        role="admin",
        password_hash=hash_password("安全密码安全密码123456"),
        must_change_password=False,
    )
    User.objects.create(
        username="editor",
        username_key="editor",
        display_name="编辑",
        role="editor",
        password_hash=hash_password("安全密码安全密码123456"),
        must_change_password=True,
    )
    client = Client()
    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "用户名" in login_page.content.decode()
    assert "密码" in login_page.content.decode()

    response = client.post("/login", {"username": "admin", "password": "安全密码安全密码123456"}, follow=True)
    assert response.redirect_chain[-1][0] == "/assets"
    response = client.get("/users")
    content = response.content.decode()
    assert response.status_code == 200
    assert "账号" in content
    assert "新增账号" in content
    assert 'readonly aria-label="用户名"' in content
    assert "选择角色" in content
    assert 'data-confirm-action="停用账号"' in content
    assert 'data-confirm-action="重置密码"' in content


@pytest.mark.e2e
@pytest.mark.django_db(databases={"default", "control"})
def test_account_navigation_hides_admin_area_for_viewer_but_server_still_denies(control_state):
    User.objects.create(
        username="viewer",
        username_key="viewer",
        display_name="只读",
        role="viewer",
        password_hash=hash_password("安全密码安全密码123456"),
        must_change_password=False,
    )
    client = Client()
    assert client.post("/login", {"username": "viewer", "password": "安全密码安全密码123456"}).status_code == 302
    page = client.get("/password")
    assert page.status_code == 200
    assert 'href="/users"' not in page.content.decode()
    denied = client.get("/users")
    assert denied.status_code == 403
