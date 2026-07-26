from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from src.auth import service as auth_service
from src.auth.schemas import ViewerContext
from src.database import get_db
from src.config import settings
from src.exceptions import UnauthorizedError, InternalServerError


bearer_auth = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    description=(
        "JWT access token. Long-term JWTs are accepted only by note creation."
    ),
    auto_error=False,
)
guest_session_auth = APIKeyHeader(
    name="X-Guest-Session-ID",
    scheme_name="GuestSession",
    description="Guest session ID for Wiz chat and video status streams.",
    auto_error=False,
)


def _require_secret_key() -> str:
    if not settings.secret_key:
        raise InternalServerError("SECRET_KEY is not configured")
    return settings.secret_key


def _get_cached_payload(
    request: Request | None,
    token: str,
) -> dict | None:
    if request is None:
        return None
    state = getattr(request, "state", None)
    if state is None:
        return None
    cached_token = getattr(state, "auth_token", None)
    if cached_token != token:
        return None
    return getattr(state, "auth_payload", None)


def get_current_user_id(
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_auth),
    request: Request = None,
) -> int:
    if not authorization:
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.credentials
    secret_key = _require_secret_key()

    try:
        payload = _get_cached_payload(request, token) or jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
        )
    except Exception:
        raise UnauthorizedError("Invalid or expired token")

    if payload.get("type") == "long_term":
        raise UnauthorizedError("Long-term tokens are not allowed for this endpoint")

    user_id = payload.get("user_id")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    return int(user_id)


def get_viewer_context(
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_auth),
    request: Request = None,
    guest_session_id: str | None = Security(guest_session_auth),
) -> ViewerContext:
    context = ViewerContext()

    if authorization:
        token = authorization.credentials
        secret_key = _require_secret_key()
        try:
            payload = _get_cached_payload(request, token) or jwt.decode(
                token,
                secret_key,
                algorithms=["HS256"],
            )
            if payload.get("type") != "long_term":
                context.user_id = int(payload.get("user_id"))
                return context
        except Exception:
            pass

    if guest_session_id:
        context.guest_session_id = guest_session_id
        return context

    raise UnauthorizedError("Missing Auth or Guest ID")


def get_current_user_id_or_long_term(
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_auth),
    request: Request = None,
    db: Session = Depends(get_db),
) -> int:
    if not authorization:
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.credentials
    secret_key = _require_secret_key()

    try:
        payload = _get_cached_payload(request, token) or jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
        )
        user_id = payload.get("user_id")
        if not user_id:
            raise UnauthorizedError("Invalid token payload")

        if payload.get("type") == "long_term":
            user = auth_service.get_user_by_id(db, int(user_id))
            if not user or user.long_term_token != token:
                raise UnauthorizedError("Invalid or revoked long-term token")

        return int(user_id)
    except UnauthorizedError:
        raise
    except Exception:
        user = auth_service.get_user_by_long_term_token(db, token)
        if user:
            return user.id
        raise UnauthorizedError("Invalid or expired token")
