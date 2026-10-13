import fcntl
import os
from datetime import timedelta
from pathlib import Path

from common.models import Job
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .gate import maintenance_gate


class WorkerBusy(RuntimeError):
    code = "WORKER_BUSY"


def _worker_lock_path() -> Path:
    configured = os.environ.get("WORKER_LOCK_FILE")
    if configured:
        return Path(configured)
    return Path(f"{settings.DATABASES['control']['NAME']}.worker")


def _lock_worker():
    path = _worker_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="ascii")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise WorkerBusy("WORKER_BUSY") from exc
    return handle


def claim_one() -> Job | None:
    with maintenance_gate():
        with transaction.atomic():
            stale = timezone.now() - timedelta(minutes=5)
            Job.objects.filter(state="running", claimed_at__lt=stale).update(state="interrupted", claimed_at=None)
            job = Job.objects.select_for_update().filter(state="queued").order_by("uuid").first()
            if not job:
                return None
            job.state, job.claimed_at, job.attempts = "running", timezone.now(), job.attempts + 1
            job.save(update_fields=["state", "claimed_at", "attempts"])
            return job


def run_once() -> Job | None:
    handle = _lock_worker()
    try:
        return claim_one()
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
