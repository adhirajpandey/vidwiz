"""
Centralized error handling for VidWiz API.

This module provides:
- Custom exception classes for common error scenarios
- Consistent JSON error response formatting
- Global exception handlers for Flask app
"""

from flask import jsonify
from pydantic import ValidationError as PydanticValidationError
from vidwiz.shared.logging import get_logger

logger = get_logger("vidwiz.errors")


# =============================================================================
# Error Codes
# =============================================================================

class ErrorCode:
    """Standard error codes for API responses."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    BAD_REQUEST = "BAD_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


# =============================================================================
# Custom Exception Classes
# =============================================================================

class APIError(Exception):
    """Base exception for all API errors."""

    def __init__(self, message: str, code: str, status_code: int, details: list = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

    def to_response(self):
        """Convert exception to Flask JSON response."""
        return create_error_response(self.code, self.message, self.details), self.status_code


class BadRequestError(APIError):
    """Raised when request is malformed (e.g., missing JSON body)."""

    def __init__(self, message: str = "Bad request", details: list = None):
        super().__init__(message, ErrorCode.BAD_REQUEST, 400, details)


class ValidationError(APIError):
    """Raised when request data fails validation."""

    def __init__(self, message: str = "Validation failed", details: list = None):
        super().__init__(message, ErrorCode.VALIDATION_ERROR, 422, details)


class NotFoundError(APIError):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Resource not found", details: list = None):
        super().__init__(message, ErrorCode.NOT_FOUND, 404, details)


class UnauthorizedError(APIError):
    """Raised when authentication is missing or invalid."""

    def __init__(self, message: str = "Unauthorized", details: list = None):
        super().__init__(message, ErrorCode.UNAUTHORIZED, 401, details)


class ForbiddenError(APIError):
    """Raised when user is authenticated but lacks permission."""

    def __init__(self, message: str = "Forbidden", details: list = None):
        super().__init__(message, ErrorCode.FORBIDDEN, 403, details)


class ConflictError(APIError):
    """Raised when request conflicts with current state (e.g., duplicate resource)."""

    def __init__(self, message: str = "Conflict", details: list = None):
        super().__init__(message, ErrorCode.CONFLICT, 409, details)


class RateLimitError(APIError):
    """Raised when rate limit or quota is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", details: list = None):
        super().__init__(message, ErrorCode.RATE_LIMIT_EXCEEDED, 429, details)


# =============================================================================
# Response Helpers
# =============================================================================

def create_error_response(code: str, message: str, details: list = None) -> dict:
    """
    Create a standardized error response dictionary.

    Args:
        code: Error code (e.g., VALIDATION_ERROR)
        message: Human-readable error message
        details: Optional list of detail objects (e.g., field-level validation errors)

    Returns:
        Standardized error response dictionary
    """
    response = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        response["error"]["details"] = details
    return response


def handle_validation_error(exc: PydanticValidationError) -> tuple:
    """
    Handle Pydantic validation errors and return standardized response.

    Args:
        exc: Pydantic ValidationError exception

    Returns:
        Tuple of (response_dict, status_code)
    """
    # Extract field-level error details from Pydantic
    details = []
    for error in exc.errors():
        detail = {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        details.append(detail)

    response = create_error_response(
        ErrorCode.VALIDATION_ERROR,
        "Request validation failed",
        details
    )
    return jsonify(response), 422


# =============================================================================
# Global Exception Handlers
# =============================================================================

def register_error_handlers(app):
    """
    Register global error handlers with the Flask app.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(APIError)
    def handle_api_error(exc):
        """Handle all custom API errors."""
        logger.warning(f"API error: {exc.code} - {exc.message}")
        return exc.to_response()

    @app.errorhandler(PydanticValidationError)
    def handle_pydantic_validation_error(exc):
        """Handle Pydantic validation errors raised during request processing."""
        logger.warning(f"Validation error: {exc}")
        return handle_validation_error(exc)

    @app.errorhandler(404)
    def handle_404(exc):
        """Handle Flask's built-in 404 errors."""
        response = create_error_response(
            ErrorCode.NOT_FOUND,
            "The requested resource was not found"
        )
        return jsonify(response), 404

    @app.errorhandler(500)
    def handle_500(exc):
        """Handle unhandled server errors."""
        logger.exception(f"Unhandled server error: {exc}")
        response = create_error_response(
            ErrorCode.INTERNAL_ERROR,
            "Internal Server Error"
        )
        return jsonify(response), 500

    @app.errorhandler(Exception)
    def handle_unhandled_exception(exc):
        """Catch-all for any unhandled exceptions."""
        logger.exception(f"Unhandled exception: {exc}")
        response = create_error_response(
            ErrorCode.INTERNAL_ERROR,
            "Internal Server Error"
        )
        return jsonify(response), 500

    logger.info("Global error handlers registered")
