import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from .passwords import hash_password


class UserManager(BaseUserManager["User"]):
    def create_user(self, username: str, password_hash: str | None = None, password: str | None = None, **extra):
        if password_hash is None:
            if password is None:
                raise ValueError("PASSWORD_REQUIRED")
            password_hash = hash_password(password)
        return self.model(username=username.strip(), username_key=username.strip().casefold(), password_hash=password_hash, **extra)

    def create_superuser(self, username: str, password_hash: str, **extra):
        extra.update(role=User.Role.ADMIN, active=True)
        return self.create_user(username, password_hash, **extra)


class User(AbstractBaseUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "管理员"
        EDITOR = "editor", "运维编辑者"
        VIEWER = "viewer", "只读用户"

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=128, unique=True)
    username_key = models.CharField(max_length=128, unique=True, editable=False)
    display_name = models.CharField(max_length=128)
    password_hash = models.CharField(max_length=256)
    role = models.CharField(max_length=16, choices=Role.choices)
    active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)
    auth_version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []  # type: ignore[misc]
    objects = UserManager()

    @property  # type: ignore[misc,override]
    def password(self) -> str:  # type: ignore[override]
        return self.password_hash

    @password.setter  # type: ignore[misc]
    def password(self, value: str) -> None:
        self.password_hash = value

    def set_password(self, raw_password: str | None) -> None:
        if raw_password is None:
            self.password_hash = "!"
        else:
            self.password_hash = hash_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        from .passwords import verify_password_equalized

        return verify_password_equalized(self.password_hash, raw_password)

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.active

    @property
    def is_staff(self) -> bool:
        return self.role == self.Role.ADMIN and self.active

    @property
    def is_superuser(self) -> bool:
        return self.role == self.Role.ADMIN and self.active

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(role__in=["admin", "editor", "viewer"]), name="user_role_valid"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="user_version_positive"),
        ]


class LoginAttemptState(models.Model):
    normalized_login_key = models.CharField(max_length=128, primary_key=True)
    window_start = models.DateTimeField()
    consecutive_failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "accounts"
