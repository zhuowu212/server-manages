from __future__ import annotations

from datetime import UTC, datetime

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.backends.base import SessionBase
from django.utils import timezone as django_timezone
from operations.gate import current_epoch

IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 8 * 60 * 60


def session_is_current(session: SessionBase, user) -> bool:
    now = django_timezone.now()
    created = session.get("_session_created_at")
    last_seen = session.get("_session_last_seen")
    if not created or not last_seen:
        return False
    if (now - datetime.fromtimestamp(created, tz=UTC)).total_seconds() > ABSOLUTE_SECONDS:
        return False
    if (now - datetime.fromtimestamp(last_seen, tz=UTC)).total_seconds() > IDLE_SECONDS:
        return False
    if str(user.uuid) != session.get(SESSION_KEY):
        return False
    if not user.active:
        return False
    if session.get("_auth_version") != user.auth_version:
        return False
    try:
        epoch = current_epoch()
    except Exception:
        return False
    return session.get("_session_epoch") == epoch


def mark_session(session: SessionBase, user) -> None:
    now = django_timezone.now().timestamp()
    epoch = current_epoch()
    session["_session_created_at"] = now
    session["_session_last_seen"] = now
    session["_auth_version"] = user.auth_version
    session["_session_epoch"] = epoch


def touch_session(session: SessionBase, user) -> None:
    session["_session_last_seen"] = django_timezone.now().timestamp()
    session["_auth_version"] = user.auth_version
