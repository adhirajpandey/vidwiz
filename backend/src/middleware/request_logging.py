import inspect
import json
import logging
import time
from typing import Any
from uuid import uuid4
from urllib.parse import parse_qs

import jwt
from fastapi import status
from fastapi.responses import JSONResponse

from src.config import settings
from src.exceptions import ErrorCode
from src.models import ErrorPayload, ErrorResponse
from src.logging import request_id_var


REDACT_FIELDS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "long_term_token",
    "authorization",
    "secret",
    "api_key",
    "key",
    "cookie",
    "set-cookie",
    "session",
    "csrf",
    "jwt",
}


def _redact_sensitive(data: Any) -> Any:
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in REDACT_FIELDS:
                redacted[key] = "***"
            else:
                redacted[key] = _redact_sensitive(value)
        return redacted
    if isinstance(data, list):
        return [_redact_sensitive(item) for item in data]
    return data


def _truncate_text(text: str, max_bytes: int) -> tuple[str, bool]:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return text, False
    truncated = data[:max_bytes].decode("utf-8", errors="replace")
    return truncated, True


def _is_json_content_type(content_type: str) -> bool:
    return "application/json" in content_type or content_type.endswith("+json")


def _is_text_content_type(content_type: str) -> bool:
    return content_type.startswith("text/")


def _serialize_body(
    body: bytes,
    content_type: str | None,
    max_bytes: int,
) -> tuple[str | None, bool, str | None]:
    if not body:
        return None, False, None

    content_type = (content_type or "").lower()
    if not content_type:
        return "<skipped: unknown content-type>", False, None

    if "text/event-stream" in content_type:
        return "<skipped: text/event-stream>", False, None

    if "application/x-www-form-urlencoded" in content_type:
        decoded = body.decode("utf-8", errors="replace")
        parsed = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(decoded).items()}
        redacted = _redact_sensitive(parsed)
        serialized = json.dumps(redacted, ensure_ascii=True, separators=(",", ":"))
        truncated, was_truncated = _truncate_text(serialized, max_bytes)
        return truncated, was_truncated, None

    if _is_json_content_type(content_type) or _is_text_content_type(content_type):
        decoded = body.decode("utf-8", errors="replace")
        parsed = None
        if _is_json_content_type(content_type) or decoded.strip().startswith("{") or decoded.strip().startswith("["):
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError:
                parsed = None

        if parsed is not None:
            redacted = _redact_sensitive(parsed)
            serialized = json.dumps(redacted, ensure_ascii=True, separators=(",", ":"))
            truncated, was_truncated = _truncate_text(serialized, max_bytes)
            return truncated, was_truncated, None

        truncated, was_truncated = _truncate_text(decoded, max_bytes)
        return truncated, was_truncated, None

    return f"<skipped: {content_type}>", False, None


def _get_endpoint_info(scope) -> tuple[str | None, str | None, int | None]:
    route = scope.get("route")
    endpoint = None
    if route is not None:
        if hasattr(route, "dependant") and getattr(route.dependant, "call", None):
            endpoint = route.dependant.call
        elif hasattr(route, "endpoint"):
            endpoint = route.endpoint
    if endpoint is None:
        endpoint = scope.get("endpoint")
    if endpoint:
        endpoint = inspect.unwrap(endpoint)
    if not endpoint:
        return None, None, None
    endpoint_name = f"{endpoint.__module__}.{endpoint.__name__}"
    code = getattr(endpoint, "__code__", None)
    if not code:
        return endpoint_name, None, None
    return endpoint_name, code.co_filename, code.co_firstlineno


def _build_log_message(method: str | None, path: str | None, status: int, duration_ms: int) -> str:
    return f"{method} {path} {status} {duration_ms}ms"


def _extract_user_info(
    headers: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    authorization = headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return {}, None, None
    secret_key = settings.secret_key
    if not secret_key:
        return {}, None, None

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    except Exception:
        return {}, None, None

    user_fields: dict[str, Any] = {}
    user_id = payload.get("user_id")
    if user_id is not None:
        try:
            user_fields["user_id"] = int(user_id)
        except (TypeError, ValueError):
            user_fields["user_id"] = user_id
    user_email = payload.get("email")
    if user_email:
        user_fields["user_email"] = user_email
    return user_fields, payload, token


def _set_scope_state(scope, key: str, value: Any) -> None:
    state = scope.get("state")
    if state is None:
        scope["state"] = {key: value}
        return
    if isinstance(state, dict):
        state[key] = value
        return
    setattr(state, key, value)


def _extract_client_ip(scope, headers: dict[str, str]) -> str | None:
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return (scope.get("client") or (None, None))[0]


def _build_base_fields(
    *,
    scope,
    headers: dict[str, str],
    status_code: int,
    duration_ms: int,
    endpoint_name: str | None,
    endpoint_file: str | None,
    endpoint_line: int | None,
) -> dict[str, Any]:
    return {
        "http_method": scope.get("method"),
        "http_path": scope.get("path"),
        "http_query": scope.get("query_string", b"").decode("latin-1"),
        "http_status": status_code,
        "duration_ms": duration_ms,
        "client_ip": _extract_client_ip(scope, headers),
        "user_agent": headers.get("user-agent"),
        "endpoint": endpoint_name,
        "endpoint_file": endpoint_file,
        "endpoint_line": endpoint_line,
    }


def _build_request_body_fields(
    *,
    body: bytes,
    content_type: str | None,
    max_bytes: int,
) -> dict[str, Any]:
    request_body_text = None
    request_body_truncated = False
    if body:
        request_body_text, request_body_truncated, _ = _serialize_body(
            body,
            content_type,
            max_bytes,
        )
    return {
        "request_content_type": content_type if body else None,
        "request_body": request_body_text,
        "request_body_bytes": len(body),
        "request_body_truncated": request_body_truncated,
    }


def _build_response_body_fields(
    *,
    body: bytes,
    content_type: str | None,
    max_bytes: int,
    response_headers: dict[str, str],
    response_body_truncated: bool,
) -> dict[str, Any]:
    response_body_text, response_body_text_truncated, _ = _serialize_body(
        body,
        content_type,
        max_bytes,
    )
    response_body_truncated = response_body_truncated or response_body_text_truncated
    return {
        "response_content_type": content_type,
        "response_body": response_body_text,
        "response_body_bytes": len(body),
        "response_content_length": response_headers.get("content-length"),
        "response_body_truncated": response_body_truncated,
    }


class RequestLoggingMiddleware:
    def __init__(
        self,
        app,
        max_request_body: int = 8192,
        max_response_body: int = 8192,
    ) -> None:
        self.app = app
        self.max_request_body = max_request_body
        self.max_response_body = max_response_body
        self.logger = logging.getLogger("vidwiz.api")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("path") == "/v2/internal/metrics":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        user_fields, auth_payload, auth_token = _extract_user_info(headers)
        if auth_payload is not None and auth_token is not None:
            _set_scope_state(scope, "auth_payload", auth_payload)
            _set_scope_state(scope, "auth_token", auth_token)
        request_id = headers.get("x-request-id") or uuid4().hex
        token = request_id_var.set(request_id)

        body = b""
        stored_messages = []
        while True:
            message = await receive()
            stored_messages.append(message)
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break

        receive_index = 0

        async def receive_with_body():
            nonlocal receive_index
            if receive_index < len(stored_messages):
                message = stored_messages[receive_index]
                receive_index += 1
                return message
            return await receive()

        status_code = 500
        response_headers: dict[str, str] = {}
        response_body = bytearray()
        response_body_truncated = False

        async def send_wrapper(message):
            nonlocal status_code, response_headers, response_body_truncated
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                headers_list = list(message.get("headers", []))
                if not any(header[0].lower() == b"x-request-id" for header in headers_list):
                    headers_list.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers_list
                response_headers = {
                    key.decode("latin-1").lower(): value.decode("latin-1")
                    for key, value in headers_list
                }
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    if len(response_body) < self.max_response_body:
                        remaining = self.max_response_body - len(response_body)
                        response_body.extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            response_body_truncated = True
                    else:
                        response_body_truncated = True
            await send(message)

        try:
            await self.app(scope, receive_with_body, send_wrapper)
        except Exception:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            endpoint_name, endpoint_file, endpoint_line = _get_endpoint_info(scope)
            base_fields = _build_base_fields(
                scope=scope,
                headers=headers,
                status_code=500,
                duration_ms=duration_ms,
                endpoint_name=endpoint_name,
                endpoint_file=endpoint_file,
                endpoint_line=endpoint_line,
            )
            base_fields.update(user_fields)
            self.logger.exception("Unhandled exception during request", extra=base_fields)

            request_content_type = headers.get("content-type")
            request_fields = _build_request_body_fields(
                body=body,
                content_type=request_content_type,
                max_bytes=self.max_request_body,
            )
            response_fields = {
                "response_content_type": None,
                "response_body": None,
                "response_body_bytes": 0,
                "response_content_length": None,
                "response_body_truncated": False,
            }
            self.logger.log(
                logging.ERROR,
                _build_log_message(scope.get("method"), scope.get("path"), 500, duration_ms),
                extra={**base_fields, **request_fields, **response_fields},
            )

            error = ErrorResponse(
                error=ErrorPayload(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Internal Server Error",
                )
            )
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error.model_dump(mode="json"),
                headers={"X-Request-ID": request_id},
            )
            await response(scope, receive_with_body, send)
            return
        else:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            endpoint_name, endpoint_file, endpoint_line = _get_endpoint_info(scope)
            request_content_type = headers.get("content-type")
            response_content_type = response_headers.get("content-type")

            base_fields = _build_base_fields(
                scope=scope,
                headers=headers,
                status_code=status_code,
                duration_ms=duration_ms,
                endpoint_name=endpoint_name,
                endpoint_file=endpoint_file,
                endpoint_line=endpoint_line,
            )
            base_fields.update(user_fields)
            request_fields = _build_request_body_fields(
                body=body,
                content_type=request_content_type,
                max_bytes=self.max_request_body,
            )
            response_fields = _build_response_body_fields(
                body=bytes(response_body),
                content_type=response_content_type,
                max_bytes=self.max_response_body,
                response_headers=response_headers,
                response_body_truncated=response_body_truncated,
            )

            level = logging.INFO
            if status_code >= 500:
                level = logging.ERROR
            elif status_code >= 400:
                level = logging.WARNING

            self.logger.log(
                level,
                _build_log_message(
                    scope.get("method"), scope.get("path"), status_code, duration_ms
                ),
                extra={**base_fields, **request_fields, **response_fields},
            )
        finally:
            request_id_var.reset(token)
