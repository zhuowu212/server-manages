from __future__ import annotations

import sqlite3

from common.db import MIN_SQLITE, connection_pragmas
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from operations.control_models import SessionEpoch
from operations.gate import maintenance_status


@require_GET
def live(_request):
    return JsonResponse({"status": "alive"})


@require_GET
def ready(_request):
    try:
        if sqlite3.sqlite_version_info < MIN_SQLITE:
            raise RuntimeError("SQLITE_RUNTIME_UNSUPPORTED")
        for alias in ("default", "control"):
            connection = connections[alias]
            connection.ensure_connection()
            values = connection_pragmas(connection.connection)
            if values != {"journal_mode": "wal", "synchronous": 2, "foreign_keys": 1, "busy_timeout": 5000, "wal_autocheckpoint": 1000}:
                raise RuntimeError("SQLITE_PRAGMA_UNSAFE")
        maintenance, _epoch = maintenance_status()
        if not SessionEpoch.objects.using("control").filter(singleton=True).exists():  # type: ignore[attr-defined]
            return JsonResponse({"status": "not_ready"}, status=503)
    except Exception:
        return JsonResponse({"status": "not_ready"}, status=503)
    if maintenance:
        return JsonResponse({"status": "maintenance"}, status=503)
    return JsonResponse({"status": "ready"})
