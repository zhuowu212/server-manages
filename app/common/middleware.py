from __future__ import annotations

import logging
import uuid

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from operations.gate import ControlStateUnavailable, MaintenanceError, maintenance_gate

from .db import is_busy_error
from .errors import DomainError, error_payload
from .logging import SafeLogger
from .responses import error_response

_logger = SafeLogger(logging.getLogger(__name__))


class RequestSafetyMiddleware:
    """Keep infrastructure failures safe and machine-readable at the edge."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        try:
            if request.path.startswith("/health/"):
                return self.get_response(request)
            with maintenance_gate():
                return self.get_response(request)
        except MaintenanceError:
            return error_response(request, "MAINTENANCE", status=503, headers={"Retry-After": "30"})
        except ControlStateUnavailable:
            return error_response(request, "NOT_READY", status=503)
        except DomainError as exc:
            return JsonResponse(error_payload(exc, request.request_id), status=exc.status)
        except PermissionDenied:
            return error_response(request, "FORBIDDEN", status=403)
        except Exception as exc:
            if is_busy_error(exc):
                return error_response(request, "DB_BUSY", status=503, headers={"Retry-After": "1"})
            _logger.warning("request_failed", request_id=request.request_id, status=500, error_code="INTERNAL_ERROR")
            return error_response(request, "INTERNAL_ERROR", status=500)

    def process_exception(self, request, exception):
        request_id = getattr(request, "request_id", str(uuid.uuid4()))
        request.request_id = request_id
        if isinstance(exception, MaintenanceError):
            return error_response(request, "MAINTENANCE", status=503, headers={"Retry-After": "30"})
        if isinstance(exception, ControlStateUnavailable):
            return error_response(request, "NOT_READY", status=503)
        if isinstance(exception, DomainError):
            return JsonResponse(error_payload(exception, request_id), status=exception.status)
        if is_busy_error(exception):
            return error_response(request, "DB_BUSY", status=503, headers={"Retry-After": "1"})
        _logger.warning("request_failed", request_id=request_id, status=500, error_code="INTERNAL_ERROR")
        return error_response(request, "INTERNAL_ERROR", status=500)
