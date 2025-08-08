"""
Centralized rate limiter setup for VidWiz.
"""
from typing import Optional
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def rate_limit_key_func() -> str:
    """Use authenticated user id when available; otherwise client IP.
    Supports proxies by honoring X-Forwarded-For when present.
    """
    user_id: Optional[int] = getattr(request, "user_id", None)
    if user_id is not None:
        return f"user:{user_id}"

    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()

    return get_remote_address()


limiter = Limiter(
    key_func=rate_limit_key_func,
    default_limits=[],  # We will specify limits per-route
)