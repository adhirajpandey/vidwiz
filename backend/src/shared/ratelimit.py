from fastapi import Request
from slowapi import Limiter

from src.config import settings


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"

limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[settings.rate_limit_default],
    headers_enabled=True,
    enabled=settings.rate_limit_enabled,
)
