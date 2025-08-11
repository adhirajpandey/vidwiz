from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request

# Shared Limiter instance with identifier priority:
# 1) CF-Connecting-IP header
# 2) authenticated user_id
# 3) remote address

def rate_limit_key():
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    user_id = getattr(request, "user_id", None)
    if user_id:
        return str(user_id)
    return get_remote_address()


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri="memory://",
    headers_enabled=True,
)


def init_rate_limiter(app):
    """Initialize the shared limiter with the Flask app."""
    limiter.init_app(app)
    return limiter