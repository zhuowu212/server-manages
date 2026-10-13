from __future__ import annotations

from django.http import JsonResponse

DEFAULT_MESSAGES = {
    "AUDIT_UNAVAILABLE": "暂时无法完成请求",
    "AUTHENTICATION_FAILED": "账号或密码错误",
    "DB_BUSY": "系统正忙，请稍后重试",
    "FORBIDDEN": "没有执行此操作的权限",
    "IDEMPOTENCY_CONFLICT": "请求幂等键已用于其他操作",
    "INTERNAL_ERROR": "系统暂时无法完成请求",
    "INVALID_JSON": "请求格式不正确",
    "MAINTENANCE": "系统维护中，请稍后重试",
    "NOT_READY": "系统暂不可用",
    "SESSION_INVALID": "登录已失效，请重新登录",
    "THROTTLED": "登录尝试过多，请稍后再试",
    "UNAUTHENTICATED": "请先登录",
    "VALIDATION_ERROR": "请求无法处理",
}


def error_response(
    request,
    code: str,
    *,
    status: int,
    message: str | None = None,
    field_errors: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JsonResponse:
    response = JsonResponse(
        {
            "code": code,
            "message": message or DEFAULT_MESSAGES.get(code, "请求无法处理"),
            "field_errors": field_errors or [],
            "request_id": getattr(request, "request_id", None),
        },
        status=status,
        headers=headers,
    )
    return response
