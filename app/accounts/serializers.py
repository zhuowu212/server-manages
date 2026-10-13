from .models import User
from .passwords import validate_password


def public_user(user: User) -> dict[str, object]:
    return {
        "id": str(user.uuid), "username": user.username, "display_name": user.display_name,
        "role": user.role, "active": user.active, "must_change_password": user.must_change_password,
        "version": user.version,
    }


def validate_create(data: dict[str, object]) -> dict[str, object]:
    required = {"username", "display_name", "role", "initial_password"}
    allowed = required | {"active"}
    if set(data) - allowed:
        raise ValueError("USER_FIELDS_INVALID")
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError("USER_FIELDS_REQUIRED")
    if not all(isinstance(data[key], str) and data[key] for key in required):
        raise ValueError("USER_FIELDS_INVALID")
    if not 1 <= len(str(data["username"]).strip()) <= 128 or not 1 <= len(str(data["display_name"]).strip()) <= 128:
        raise ValueError("USER_FIELDS_INVALID")
    if data["role"] not in User.Role.values:
        raise ValueError("ROLE_INVALID")
    if "active" in data and not isinstance(data["active"], bool):
        raise ValueError("ACTIVE_INVALID")
    validate_password(str(data["initial_password"]))
    return data
