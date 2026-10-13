import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("contenttypes", "0002_remove_content_type_name")]
    operations = [migrations.CreateModel(
        name="User",
        fields=[
            ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
            ("username", models.CharField(max_length=128)),
            ("username_key", models.CharField(editable=False, max_length=128, unique=True)),
            ("display_name", models.CharField(max_length=128)),
            ("password_hash", models.CharField(max_length=256)),
            ("role", models.CharField(choices=[("admin", "管理员"), ("editor", "运维编辑者"), ("viewer", "只读用户")], max_length=16)),
            ("active", models.BooleanField(default=True)),
            ("must_change_password", models.BooleanField(default=True)),
            ("version", models.PositiveBigIntegerField(default=1)),
            ("auth_version", models.PositiveBigIntegerField(default=1)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ],
        options={"constraints": [
            models.CheckConstraint(condition=models.Q(role__in=["admin", "editor", "viewer"]), name="user_role_valid"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="user_version_positive"),
        ]},
    ), migrations.CreateModel(
        name="LoginAttemptState",
        fields=[
            ("normalized_login_key", models.CharField(max_length=128, primary_key=True, serialize=False)),
            ("window_start", models.DateTimeField()),
            ("consecutive_failures", models.PositiveIntegerField(default=0)),
            ("locked_until", models.DateTimeField(blank=True, null=True)),
        ],
    )]
