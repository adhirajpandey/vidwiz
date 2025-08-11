try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from flask import request
    _FLASK_LIMITER_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when dependency is missing
    Limiter = None  # type: ignore
    get_remote_address = None  # type: ignore

    class _NoopLimiter:
        def init_app(self, app):
            return self

        def limit(self, *args, **kwargs):
            def _decorator(obj):
                return obj

            return _decorator

    limiter = _NoopLimiter()  # type: ignore
    _FLASK_LIMITER_AVAILABLE = False
else:
    # Create a shared Limiter instance with a key function that prioritizes authenticated user_id
    # and falls back to client IP address for unauthenticated routes.
    limiter = Limiter(
        key_func=lambda: str(getattr(request, "user_id", None))
        if getattr(request, "user_id", None)
        else get_remote_address(),
        storage_uri="memory://",
    )


def init_rate_limiter(app):
    """Initialize the shared limiter with the Flask app."""
    limiter.init_app(app)
    return limiter