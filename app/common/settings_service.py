from __future__ import annotations

from common.models import SystemSetting

ALLOWED_KEYS: frozenset[str] = frozenset()


def validate_business_settings(*, using: str = "default") -> None:
    """Q12: the first release has a deliberately empty setting allowlist."""
    if SystemSetting.objects.using(using).exists():
        raise ValueError("BUSINESS_SETTING_NOT_ALLOWED")


def set_business_setting(key: str, typed_value: object, *, using: str = "default") -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError("BUSINESS_SETTING_NOT_ALLOWED")
    # Kept as an explicit guard so enabling a future key cannot accidentally
    # bypass the database CHECK(0) migration policy.
    SystemSetting.objects.using(using).update_or_create(key=key, defaults={"typed_value": typed_value})
