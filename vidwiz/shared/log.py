import logging
import os
import sys
from typing import Optional


_LOGGER_CONFIGURED = False


def _determine_log_level() -> int:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def init_logging(default_level: Optional[int] = None) -> None:
    """
    Initialize root logging once with a sensible formatter and level.
    Safe to call multiple times; configuration will only be applied once.
    """
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED:
        return

    level = default_level if default_level is not None else _determine_log_level()

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        root_logger.setLevel(level)

    # Quiet overly chatty libraries unless explicitly overridden
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _LOGGER_CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a named logger and ensure logging is initialized."""
    init_logging()
    return logging.getLogger(name if name else __name__)