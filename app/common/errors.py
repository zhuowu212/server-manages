import re


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status = 422
    message = "请求无法处理"

    def __init__(self, message: str | None = None, *, field_errors: list[dict[str, str]] | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.field_errors = field_errors or []


class AuthorizationError(DomainError):
    code = "FORBIDDEN"
    status = 403


class ConflictError(DomainError):
    code = "CONFLICT"
    status = 409


class BusyError(DomainError):
    code = "DB_BUSY"
    status = 503
    message = "系统正忙，请稍后重试"


class AuditUnavailable(DomainError):
    code = "AUDIT_UNAVAILABLE"
    status = 503
    message = "暂时无法完成请求"


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"


class AuthenticationError(DomainError):
    code = "AUTHENTICATION_FAILED"
    status = 401


def error_payload(error: DomainError, request_id: str | None = None) -> dict[str, object]:
    return {
        "code": error.code,
        "message": error.message,
        "field_errors": error.field_errors,
        "request_id": request_id,
    }


_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


def safe_error_code(exc: BaseException, fallback: str = "REQUEST_INVALID") -> str:
    value = str(exc)
    return value if _SAFE_CODE.fullmatch(value) else fallback
