from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=2)
# A fixed valid Argon2id value makes unknown-user authentication take the same
# verification path without ever storing or logging the submitted password.
_DUMMY_HASH = _hasher.hash("server-manages-unknown-user-dummy")


def validate_password(value: str) -> None:
    if not isinstance(value, str) or not 12 <= len(value) <= 256:
        raise ValueError("PASSWORD_LENGTH_INVALID")


def hash_password(value: str) -> str:
    validate_password(value)
    return _hasher.hash(value)


def verify_password(encoded: str, value: str) -> bool:
    try:
        return _hasher.verify(encoded, value)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def verify_password_equalized(encoded: str | None, value: str) -> bool:
    """Verify a real or dummy hash so unknown usernames have equal work."""
    return verify_password(encoded or _DUMMY_HASH, value)


def needs_rehash(encoded: str) -> bool:
    try:
        return _hasher.check_needs_rehash(encoded)
    except ValueError:
        return True
