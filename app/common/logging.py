from __future__ import annotations

import logging
from collections.abc import Mapping

_ALLOWED_KEYS = frozenset({"request_id", "route_name", "method", "status", "duration_ms", "error_code"})
_SENSITIVE_MARKERS = ("password", "hash", "token", "authorization", "cookie", "secret", "private_key", "credential_ref", "confirmation")


def safe_fields(fields: dict[str, object]) -> dict[str, object]:
    """Return only the stable, non-secret operational logging contract."""
    return {
        key: _safe_value(value)
        for key, value in fields.items()
        if key in _ALLOWED_KEYS and not _contains_secret_marker(key)
    }


def _contains_secret_marker(key: object) -> bool:
    normalized = str(key).casefold()
    return any(marker in normalized for marker in _SENSITIVE_MARKERS)


def _safe_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _safe_value(child)
            for key, child in value.items()
            if not _contains_secret_marker(key)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(child) for child in value]
    return value


class SafeLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def info(self, message: str, **fields: object) -> None:
        self.logger.info(message, extra={"fields": safe_fields(fields)})

    def warning(self, message: str, **fields: object) -> None:
        self.logger.warning(message, extra={"fields": safe_fields(fields)})
