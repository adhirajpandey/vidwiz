from typing import Iterable

from fastapi import HTTPException, status

from src.models import ErrorDetail, ErrorPayload, ErrorResponse


class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    BAD_REQUEST = "BAD_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class APIError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        details: Iterable[ErrorDetail] | dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        if details is None:
            self.details = None
        elif isinstance(details, dict):
            self.details = details
        else:
            self.details = list(details)

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            error=ErrorPayload(
                code=self.code,
                message=self.message,
                details=self.details,
            )
        )


class BadRequestError(APIError):
    def __init__(self, message: str = "Bad request", details=None) -> None:
        super().__init__(
            message, ErrorCode.BAD_REQUEST, status.HTTP_400_BAD_REQUEST, details
        )


class ValidationError(APIError):
    def __init__(self, message: str = "Validation failed", details=None) -> None:
        super().__init__(
            message,
            ErrorCode.VALIDATION_ERROR,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            details,
        )


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found", details=None) -> None:
        super().__init__(
            message, ErrorCode.NOT_FOUND, status.HTTP_404_NOT_FOUND, details
        )


class UnauthorizedError(APIError):
    def __init__(self, message: str = "Unauthorized", details=None) -> None:
        super().__init__(
            message, ErrorCode.UNAUTHORIZED, status.HTTP_401_UNAUTHORIZED, details
        )


class ForbiddenError(APIError):
    def __init__(self, message: str = "Forbidden", details=None) -> None:
        super().__init__(
            message, ErrorCode.FORBIDDEN, status.HTTP_403_FORBIDDEN, details
        )


class ConflictError(APIError):
    def __init__(self, message: str = "Conflict", details=None) -> None:
        super().__init__(message, ErrorCode.CONFLICT, status.HTTP_409_CONFLICT, details)


class RateLimitError(APIError):
    def __init__(self, message: str = "Rate limit exceeded", details=None) -> None:
        super().__init__(
            message,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            status.HTTP_429_TOO_MANY_REQUESTS,
            details,
        )


class InternalServerError(APIError):
    def __init__(self, message: str = "Internal server error", details=None) -> None:
        super().__init__(
            message,
            ErrorCode.INTERNAL_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            details,
        )


HTTP_STATUS_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorCode.VALIDATION_ERROR,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMIT_EXCEEDED,
    status.HTTP_500_INTERNAL_SERVER_ERROR: ErrorCode.INTERNAL_ERROR,
}


def http_exception(message: str, status_code: int) -> HTTPException:
    code = HTTP_STATUS_CODE_MAP.get(status_code, ErrorCode.INTERNAL_ERROR)
    return HTTPException(
        status_code=status_code, detail=message, headers={"X-Error-Code": code}
    )
