import pytest
import time_machine


@pytest.fixture
def clock():
    with time_machine.travel("2026-10-12T00:00:00+00:00", tick=False) as traveller:
        yield traveller


@pytest.fixture
def fault(monkeypatch):
    def inject(module, name, error):
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr(module, name, fail)
    return inject


@pytest.fixture
def role_factory(db):
    def create(role="viewer", *, must_change=False, password="测试长口令123456", **fields):
        import uuid

        from accounts.models import User
        from accounts.passwords import hash_password

        username = fields.pop("username", "test-" + uuid.uuid4().hex)
        return User.objects.create(
            username=username, username_key=username.strip().casefold(), display_name=username,
            password_hash=hash_password(password), role=role,
            must_change_password=must_change, **fields,
        )
    return create


@pytest.fixture
def control_state(db):
    """Initialize the control singleton through the same explicit test path."""
    from operations.gate import ensure_control_state

    return ensure_control_state()
