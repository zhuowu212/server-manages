import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from django.db import transaction

from .control_models import SessionEpoch


class MaintenanceError(RuntimeError):
    code = "MAINTENANCE"

    status = 503


class ControlStateUnavailable(RuntimeError):
    code = "NOT_READY"

    status = 503


def _gate_path() -> Path:
    configured = os.environ.get("CONTROL_GATE_FILE")
    if configured:
        return Path(configured)
    from django.conf import settings

    return Path(f"{settings.DATABASES['control']['NAME']}.gate")


@contextmanager
def _shared_file_gate() -> Iterator[None]:
    path = _gate_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="ascii")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise MaintenanceError("MAINTENANCE") from exc
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


@contextmanager
def _exclusive_file_gate(*, blocking: bool = True) -> Iterator[None]:
    path = _gate_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="ascii")
    try:
        flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        fcntl.flock(handle.fileno(), flags)
    except OSError as exc:
        handle.close()
        raise MaintenanceError("MAINTENANCE") from exc
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _control_state() -> SessionEpoch:
    try:
        state = SessionEpoch.objects.using("control").filter(singleton=True).first()  # type: ignore[attr-defined]
    except Exception as exc:
        raise ControlStateUnavailable("CONTROL_STATE_UNAVAILABLE") from exc
    if state is None:
        raise ControlStateUnavailable("CONTROL_STATE_MISSING")
    return state


def current_epoch() -> int:
    return int(_control_state().epoch)


@contextmanager
def maintenance_gate():
    """Check the control gate at the start of one short business unit.

    The control transaction is deliberately released before the caller does
    business work.  This prevents a request from holding the control database
    lock while it parses input or hashes a password.
    """
    with _shared_file_gate():
        with transaction.atomic(using="control"):
            state = _control_state()
            if state.maintenance:
                raise MaintenanceError("MAINTENANCE")
        yield state


@contextmanager
def exclusive_maintenance():
    with transaction.atomic(using="control"):
        state = SessionEpoch.objects.using("control").select_for_update().filter(singleton=True).first()  # type: ignore[attr-defined]
        if state is None:
            raise ControlStateUnavailable("CONTROL_STATE_MISSING")
        if state.maintenance:
            raise MaintenanceError("MAINTENANCE")
        state.maintenance = True
        state.save(using="control", update_fields=["maintenance"])
    try:
        with _exclusive_file_gate():
            yield state
    except BaseException:
        # Keep the gate closed after a failed exclusive operation until
        # recovery code explicitly reopens it.
        raise
    else:
        with transaction.atomic(using="control"):
            state = SessionEpoch.objects.using("control").select_for_update().get(singleton=True)  # type: ignore[attr-defined]
            state.maintenance = False
            state.save(using="control", update_fields=["maintenance"])


def maintenance_status() -> tuple[bool, int]:
    state = _control_state()
    return bool(state.maintenance), int(state.epoch)


@contextmanager
def control_epoch_bump(*, maintenance: bool | None = None) -> Iterator[SessionEpoch]:
    with transaction.atomic(using="control"):
        state = SessionEpoch.objects.using("control").select_for_update().filter(singleton=True).first()  # type: ignore[attr-defined]
        if state is None:
            raise ControlStateUnavailable("CONTROL_STATE_MISSING")
        state.epoch += 1
        if maintenance is not None:
            state.maintenance = maintenance
        state.save(using="control", update_fields=["epoch", "maintenance"])
        yield state


def ensure_control_state() -> SessionEpoch:
    """Create the singleton only from the explicit controlled migration path."""
    state, _ = SessionEpoch.objects.using("control").get_or_create(singleton=True)  # type: ignore[attr-defined]
    return state
