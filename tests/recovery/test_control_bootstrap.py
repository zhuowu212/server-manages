import sqlite3
import threading
import time
import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.test import Client


@pytest.mark.django_db(databases={"default", "control"})
def test_control_database_is_separate():
    assert connections["default"].settings_dict["NAME"] != connections["control"].settings_dict["NAME"]
    assert connections["default"].connection is not connections["control"].connection


def test_unsupported_sqlite_fails_ready(monkeypatch):
    from common import db

    monkeypatch.setattr(db.sqlite3, "sqlite_version_info", (3, 37, 2))
    with pytest.raises(RuntimeError, match="SQLITE_RUNTIME_UNSUPPORTED"):
        db.configure_connection(sqlite3.connect(":memory:"))


@pytest.mark.django_db(databases={"default", "control"})
def test_control_gate_is_shared_by_worker_and_app():
    from operations.control_models import SessionEpoch
    from operations.gate import MaintenanceError, maintenance_gate

    SessionEpoch.objects.using("control").create(singleton=True, maintenance=True)
    with pytest.raises(MaintenanceError):
        with maintenance_gate():
            pass


@pytest.mark.django_db(databases={"default", "control"})
def test_missing_control_state_fails_ready_and_business_gate():
    from operations.gate import ControlStateUnavailable, maintenance_gate

    response = Client().get("/health/ready")
    assert response.status_code == 503
    with pytest.raises(ControlStateUnavailable):
        with maintenance_gate():
            pass


@pytest.mark.django_db(databases={"default", "control"})
def test_failed_exclusive_maintenance_stays_closed(control_state):
    from operations.control_models import SessionEpoch
    from operations.gate import exclusive_maintenance

    with pytest.raises(RuntimeError, match="operation failed"):
        with exclusive_maintenance():
            raise RuntimeError("operation failed")
    assert SessionEpoch.objects.using("control").get(singleton=True).maintenance is True


@pytest.mark.django_db(databases={"default", "control"})
def test_shared_gate_blocks_exclusive_gate(control_state):
    from operations.gate import MaintenanceError, _exclusive_file_gate, maintenance_gate

    with maintenance_gate():
        with pytest.raises(MaintenanceError):
            with _exclusive_file_gate(blocking=False):
                pass


@pytest.mark.django_db(transaction=True, databases={"default", "control"})
def test_exclusive_maintenance_closes_gate_before_waiting_for_active_requests(control_state):
    from operations.gate import MaintenanceError, exclusive_maintenance, maintenance_gate

    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    def run_exclusive():
        try:
            with exclusive_maintenance():
                entered.set()
                release.wait(timeout=5)
        except BaseException as exc:
            errors.append(exc)
            entered.set()

    with maintenance_gate():
        thread = threading.Thread(target=run_exclusive)
        thread.start()
        deadline = time.monotonic() + 5
        blocked = False
        while time.monotonic() < deadline:
            try:
                with maintenance_gate():
                    pass
            except MaintenanceError:
                blocked = True
                break
            time.sleep(0.01)
        assert blocked
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert not errors
    assert entered.is_set()


@pytest.mark.django_db(databases={"default", "control"})
def test_worker_uses_single_process_lock(control_state):
    from operations.jobs import WorkerBusy, _lock_worker, run_once

    handle = _lock_worker()
    try:
        with pytest.raises(WorkerBusy):
            run_once()
    finally:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


@pytest.mark.django_db(databases={"default", "control"})
def test_worker_obeys_maintenance_gate(control_state):
    from common.models import Job
    from operations.control_models import SessionEpoch
    from operations.gate import MaintenanceError
    from operations.jobs import run_once

    Job.objects.create(uuid=uuid.uuid4(), kind="noop", operation_uuid=uuid.uuid4())
    state = SessionEpoch.objects.using("control").get(singleton=True)
    state.maintenance = True
    state.save(using="control", update_fields=["maintenance"])
    with pytest.raises(MaintenanceError):
        run_once()
    assert Job.objects.get().state == "queued"


@pytest.mark.django_db(databases={"default", "control"})
def test_worker_does_not_automatically_replay_stale_running_jobs(control_state):
    from datetime import timedelta

    from common.models import Job
    from django.utils import timezone
    from operations.jobs import run_once

    job = Job.objects.create(
        uuid=uuid.uuid4(),
        kind="import",
        state="running",
        claimed_at=timezone.now() - timedelta(minutes=6),
        operation_uuid=uuid.uuid4(),
    )
    assert run_once() is None
    job.refresh_from_db()
    assert job.state == "interrupted"
    assert job.claimed_at is None


@pytest.mark.django_db(databases={"default", "control"})
def test_bootstrap_admin_cli_obeys_maintenance_gate(control_state, tmp_path):
    from accounts.models import User
    from operations.control_models import SessionEpoch

    password_file = tmp_path / "admin_password"
    password_file.write_text("安全密码安全密码123456", encoding="utf-8")
    state = SessionEpoch.objects.using("control").get(singleton=True)
    state.maintenance = True
    state.save(using="control", update_fields=["maintenance"])
    with pytest.raises(CommandError, match="MAINTENANCE"):
        call_command("bootstrap_admin", username="admin", password_file=str(password_file))
    assert User.objects.count() == 0


@pytest.mark.django_db(transaction=True, databases={"default", "control"})
def test_control_migration_command_is_the_initialization_boundary():
    from operations.control_models import SessionEpoch

    SessionEpoch.objects.using("control").all().delete()
    call_command("migrate_locked", database="control", verbosity=0)
    connections["control"].close()
    connections["control"].connect()
    state = SessionEpoch.objects.using("control").get(singleton=True)
    assert state.epoch == 1
    assert state.maintenance is False


@pytest.mark.django_db(transaction=True, databases={"default", "control"})
def test_control_migration_initialization_is_repeatable_without_epoch_change(control_state):
    from operations.control_models import SessionEpoch

    state = SessionEpoch.objects.using("control").get(singleton=True)
    state.epoch = 7
    state.save(using="control", update_fields=["epoch"])
    call_command("migrate_locked", database="control", verbosity=0)
    assert SessionEpoch.objects.using("control").count() == 1
    assert SessionEpoch.objects.using("control").get(singleton=True).epoch == 7


@pytest.mark.django_db(databases={"default", "control"})
def test_database_router_keeps_business_models_out_of_control_database(control_state):
    control_tables = set(connections["control"].introspection.table_names())
    default_tables = set(connections["default"].introspection.table_names())

    assert "operations_sessionepoch" in control_tables
    assert "accounts_user" not in control_tables
    assert "common_operationreceipt" not in control_tables
    assert "accounts_user" in default_tables
    assert "operations_sessionepoch" not in default_tables


@pytest.mark.django_db(databases={"default", "control"})
def test_recovery_status_reports_non_secret_control_state(control_state, capsys):
    from operations.control_models import RestoreOperation

    RestoreOperation.objects.using("control").create(
        uuid=uuid.uuid4(),
        phase="VALIDATING",
        old_generation=uuid.uuid4(),
        new_generation=uuid.uuid4(),
        epoch=2,
        receipt_digest="digest-without-secret",
        error_code="",
    )
    call_command("recovery_status")
    output = capsys.readouterr().out
    assert "VALIDATING" in output
    assert "digest-without-secret" not in output
    assert "password" not in output.casefold()
    assert "token" not in output.casefold()
