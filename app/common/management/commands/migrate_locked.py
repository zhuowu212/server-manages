from __future__ import annotations

import fcntl
import os
from pathlib import Path

from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections


class Command(BaseCommand):
    help = "Run business and control migrations under one host lock"

    def add_arguments(self, parser):
        parser.add_argument("--database", choices=["all", "default", "control"], default="all")

    def handle(self, *args, **options):
        names = ["default", "control"] if options["database"] == "all" else [options["database"]]
        lock_path = os.environ.get("MIGRATION_LOCK", "/tmp/server-manages-migrate.lock")
        Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise CommandError("MIGRATION_LOCK_BUSY") from exc
            for name in names:
                call_command("migrate", database=name, interactive=False, verbosity=options.get("verbosity", 1))
            if "control" in names:
                from operations.gate import ensure_control_state

                ensure_control_state()
            for name in names:
                connections[name].close()
