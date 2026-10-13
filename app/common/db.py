from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from django.db import close_old_connections
from django.db.utils import OperationalError as DjangoOperationalError

MIN_SQLITE = (3, 51, 3)


def configure_connection(connection: sqlite3.Connection) -> None:
    """Apply the durability and isolation contract to every raw connection."""
    if sqlite3.sqlite_version_info < MIN_SQLITE:
        raise RuntimeError("SQLITE_RUNTIME_UNSUPPORTED")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA wal_autocheckpoint=1000")
    values = connection_pragmas(connection)
    expected = {"journal_mode": "wal", "synchronous": 2, "foreign_keys": 1,
                "busy_timeout": 5000, "wal_autocheckpoint": 1000}
    if values != expected:
        raise RuntimeError("SQLITE_PRAGMA_UNSAFE")


def configure_django_connection(sender, connection, **kwargs) -> None:
    if connection.vendor == "sqlite" and connection.connection is not None:
        configure_connection(connection.connection)


def connection_pragmas(connection: sqlite3.Connection) -> dict[str, object]:
    return {
        "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
        "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0],
        "foreign_keys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
        "busy_timeout": connection.execute("PRAGMA busy_timeout").fetchone()[0],
        "wal_autocheckpoint": connection.execute("PRAGMA wal_autocheckpoint").fetchone()[0],
    }


@contextmanager
def independent_work_unit(using: str = "default") -> Iterator[None]:
    """Give a request/worker unit a fresh Django connection and close it on exit."""
    close_old_connections()
    from django.db import connections

    connections[using].close_if_unusable_or_obsolete()
    try:
        yield
    finally:
        connections[using].close()


def is_busy_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        message = str(current).casefold()
        if isinstance(current, (sqlite3.OperationalError, DjangoOperationalError)) and (
            "database is locked" in message or "database is busy" in message
        ):
            return True
        current = current.__cause__ or current.__context__
    return False
