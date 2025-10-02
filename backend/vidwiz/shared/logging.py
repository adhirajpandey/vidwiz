import logging
import os
import sys
from typing import Optional


_CONFIGURED: bool = False


def configure_logging(level_name: Optional[str] = None) -> None:
    """Configure root logging once with a sensible console handler.

    - Level can be controlled via LOG_LEVEL env or provided argument
    - Logs are emitted to stdout in a concise, structured text format
    - Safe to call multiple times; subsequent calls are no-ops
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    effective_level_name = (level_name or os.getenv("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, effective_level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if something configured it before
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured via configure_logging()."""
    configure_logging()
    return logging.getLogger(name)
