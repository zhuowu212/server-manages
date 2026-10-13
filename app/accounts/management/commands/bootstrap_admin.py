from pathlib import Path

from audit.services import record_event
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from operations.gate import MaintenanceError, maintenance_gate

from accounts.models import User
from accounts.passwords import hash_password, validate_password


class Command(BaseCommand):
    help = "Create the first administrator from an external password file"

    def add_arguments(self, parser):
        parser.add_argument("--password-file", required=True)
        parser.add_argument("--username", default=None)

    def handle(self, *args, **options):
        if User.objects.exists():
            raise CommandError("ADMIN_ALREADY_INITIALIZED")
        username = options["username"] or __import__("os").environ.get("ADMIN_USERNAME")
        if not username:
            raise CommandError("ADMIN_USERNAME_REQUIRED")
        password = Path(options["password_file"]).read_text(encoding="utf-8").rstrip("\n")
        try:
            validate_password(password)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        password_hash = hash_password(password)
        try:
            with maintenance_gate():
                with transaction.atomic():
                    user = User.objects.create(
                        username=username.strip(), username_key=username.strip().casefold(), display_name=username.strip(),
                        role=User.Role.ADMIN, active=True, must_change_password=True, password_hash=password_hash,
                    )
                    record_event(category="account", action="user_created", result="success", actor_uuid=user.uuid, summary={"changed": True})
        except MaintenanceError as exc:
            raise CommandError("MAINTENANCE") from exc
        self.stdout.write("首个管理员已初始化；首次登录必须修改密码")
