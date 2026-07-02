"""Base application exception hierarchy.

Every exception maps to an HTTP status code and a stable machine-readable
``code`` that surfaces in the response envelope.
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base class for all handled application errors."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(
        self,
        message: str = "Bad request",
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class ValidationError(AppException):
    """Request failed domain/schema validation."""

    status_code = 422
    code = "validation_error"

    def __init__(self, message: str = "Validation failed", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class UnauthorizedError(AppException):
    """Authentication is missing or invalid."""

    status_code = 401
    code = "unauthorized"

    def __init__(self, message: str = "Authentication required", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class ForbiddenError(AppException):
    """Authenticated but lacking permission."""

    status_code = 403
    code = "forbidden"

    def __init__(self, message: str = "Insufficient permissions", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class NotFoundError(AppException):
    """A requested resource does not exist."""

    status_code = 404
    code = "not_found"

    def __init__(self, message: str = "Resource not found", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class ConflictError(AppException):
    """The request conflicts with existing state."""

    status_code = 409
    code = "conflict"

    def __init__(self, message: str = "Resource conflict", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class RateLimitError(AppException):
    """Rate limit exceeded."""

    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str = "Rate limit exceeded", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class WorkerError(AppException):
    """A camera worker could not be started or stopped."""

    status_code = 500
    code = "worker_error"

    def __init__(self, message: str = "Worker operation failed", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
