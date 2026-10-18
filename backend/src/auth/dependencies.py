from fastapi import Depends, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from src.auth import service as auth_service
from src.auth.schemas import ViewerContext
from src.database import get_db
from src.config import settings
from src.exceptions import UnauthorizedError


bearer_auth = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    description=(
        "JWT access token, or a personal API token on capture endpoints."
    ),
    auto_error=False,
)
guest_session_auth = APIKeyHeader(
    name="X-Guest-Session-ID",
    scheme_name="GuestSession",
    description="Guest session ID for Wiz chat and video status streams.",
    auto_error=False,
)


def _decode(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def get_current_user_id(
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_auth),
) -> int:
    if not authorization:
        raise UnauthorizedError("Missing or invalid Authorization header")

    try:
        payload = _decode(authorization.credentials)
    except Exception:
        raise UnauthorizedError("Invalid or expired token")

    if payload.get("type") == "long_term":
        raise UnauthorizedError("API tokens are not allowed for this endpoint")

    user_id = payload.get("user_id")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    return int(user_id)


def get_viewer_context(
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_auth),
    guest_session_id: str | None = Security(guest_session_auth),
) -> ViewerContext:
    if authorization:
        try:
            payload = _decode(authorization.credentials)
            if payload.get("type") != "long_term":
                return ViewerContext(user_id=int(payload.get("user_id")))
        except Exception:
            pass

    if guest_session_id:
        return ViewerContext(guest_session_id=guest_session_id)

    raise UnauthorizedError("Missing Auth or Guest ID")


def get_current_user_id_or_api_token(
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_auth),
    db: Session = Depends(get_db),
) -> int:
    """Accept a web session JWT or a personal API token (capture clients)."""
    if not authorization:
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.credentials
    try:
        payload = _decode(token)
    except Exception:
        payload = None

    # Legacy long-term tokens are JWTs too; they are checked by hash like
    # any other API token.
    if payload and payload.get("type") != "long_term" and payload.get("user_id"):
        return int(payload["user_id"])

    user_id = auth_service.authenticate_api_token(db, token)
    if user_id is None:
        raise UnauthorizedError("Invalid, expired, or revoked token")
    return user_id
