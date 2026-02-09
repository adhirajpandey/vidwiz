import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from typing import Any


request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_listener: QueueListener | None = None
_configured = False

LOKI_EXCLUDED_PATHS = {
    "/v2/internal/tasks",
}

_STANDARD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "message",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
}

_EXTRA_EXCLUDE_KEYS = {
    "endpoint",
    "endpoint_file",
    "endpoint_line",
    "request_id",
    "message",
    "http_method",
    "http_path",
    "http_query",
    "http_status",
    "duration_ms",
    "client_ip",
    "user_agent",
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        endpoint = getattr(record, "endpoint", None)
        endpoint_file = getattr(record, "endpoint_file", None)
        endpoint_line = getattr(record, "endpoint_line", None)
        if endpoint:
            payload["endpoint"] = endpoint
        if endpoint_file and endpoint_line:
            payload["endpoint_source"] = f"{endpoint_file}:{endpoint_line}"
        if not endpoint and record.pathname and record.lineno:
            payload["source"] = f"{record.pathname}:{record.lineno}"
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        for key in (
            "http_method",
            "http_path",
            "http_query",
            "http_status",
            "duration_ms",
            "client_ip",
            "user_agent",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        extra: dict[str, Any] = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS and key not in _EXTRA_EXCLUDE_KEYS
        }
        if extra:
            payload["extra"] = extra

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True, default=str)


class PrettyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        request_id = getattr(record, "request_id", None)
        prefix = f"{timestamp} {record.levelname} {record.name}"
        if request_id:
            prefix = f"{prefix} request_id={request_id}"

        endpoint = getattr(record, "endpoint", None)
        endpoint_file = getattr(record, "endpoint_file", None)
        endpoint_line = getattr(record, "endpoint_line", None)
        if endpoint and endpoint_file and endpoint_line:
            prefix = f"{prefix} endpoint={endpoint} source={endpoint_file}:{endpoint_line}"
        elif record.pathname and record.lineno:
            prefix = f"{prefix} source={record.pathname}:{record.lineno}"

        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"

        return f"{prefix} - {message}"


class LokiPathFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        http_path = getattr(record, "http_path", None)
        if http_path and http_path in LOKI_EXCLUDED_PATHS:
            return False
        return True


def setup_logging(settings) -> None:
    global _configured, _listener
    if _configured:
        return

    log_level = getattr(settings, "log_level", "INFO")
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    queue: Queue = Queue(-1)
    queue_handler = QueueHandler(queue)
    queue_handler.addFilter(RequestIdFilter())
    root_logger.addHandler(queue_handler)

    handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(PrettyFormatter())
    handlers.append(stream_handler)

    loki_url = getattr(settings, "loki_url", None)
    if loki_url:
        try:
            from logging_loki import LokiHandler

            loki_auth = None
            loki_username = getattr(settings, "loki_username", None)
            loki_password = getattr(settings, "loki_password", None)
            if loki_username or loki_password:
                loki_auth = (loki_username or "", loki_password or "")

            tags = {
                "service": getattr(settings, "log_service_name", "vidwiz-api"),
                "environment": getattr(settings, "environment", "unknown"),
            }

            loki_handler = LokiHandler(
                url=loki_url,
                tags=tags,
                auth=loki_auth,
                version="1",
            )
            loki_handler.setLevel(log_level)
            loki_handler.setFormatter(JsonFormatter())
            loki_handler.addFilter(LokiPathFilter())
            handlers.append(loki_handler)
        except Exception:
            root_logger.exception("Failed to configure Loki handler")
    else:
        root_logger.warning("LOKI_URL not configured; Loki logging disabled")

    _listener = QueueListener(queue, *handlers, respect_handler_level=True)
    _listener.start()
    _configured = True


def shutdown_logging() -> None:
    global _listener, _configured
    if _listener:
        _listener.stop()
        _listener = None
    _configured = False
