import hashlib
import secrets


def issue_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def token_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_confirmation_payload(actions: list[str], proposed_changes: dict[str, object]) -> tuple[list[str], dict[str, object]]:
    forbidden = {"password", "password_hash", "token", "private_key", "credential_ref", "confirmation_id"}
    if any(key.casefold() in forbidden for key in proposed_changes):
        raise ValueError("CONFIRMATION_SECRET_FIELD")
    return sorted(set(actions)), dict(proposed_changes)
