from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from src.auth import service as auth_service
from src.auth.dependencies import (
    get_current_user_id,
    get_current_user_id_or_api_token,
    get_viewer_context,
)
from src.config import settings
from src.exceptions import UnauthorizedError


def bearer_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def make_access_token(user_id: int, email: str = "user@example.com") -> str:
    return jwt.encode(
        {"user_id": user_id, "email": email, "name": "User"},
        settings.secret_key,
        algorithm="HS256",
    )


def make_long_term_token(user_id: int, email: str = "user@example.com") -> str:
    return jwt.encode(
        {"user_id": user_id, "email": email, "type": "long_term"},
        settings.secret_key,
        algorithm="HS256",
    )


def test_get_current_user_id_accepts_valid_token():
    token = make_access_token(42)
    assert get_current_user_id(bearer_credentials(token)) == 42


def test_get_current_user_id_rejects_long_term_token():
    token = make_long_term_token(42)
    with pytest.raises(UnauthorizedError):
        get_current_user_id(bearer_credentials(token))


def test_get_current_user_id_rejects_invalid_payload():
    token = jwt.encode(
        {"email": "missing@example.com"},
        settings.secret_key,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        get_current_user_id(bearer_credentials(token))


def test_get_current_user_id_rejects_expired_token():
    token = jwt.encode(
        {
            "user_id": 1,
            "email": "expired@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        get_current_user_id(bearer_credentials(token))


def test_get_current_user_id_rejects_missing_header():
    with pytest.raises(UnauthorizedError):
        get_current_user_id(None)


def test_get_viewer_context_prefers_auth():
    token = make_access_token(7)
    context = get_viewer_context(
        authorization=bearer_credentials(token),
        guest_session_id="guest-1",
    )
    assert context.user_id == 7
    assert context.guest_session_id is None


def test_get_viewer_context_falls_back_to_guest():
    context = get_viewer_context(authorization=None, guest_session_id="guest-2")
    assert context.user_id is None
    assert context.guest_session_id == "guest-2"


def test_get_viewer_context_requires_auth_or_guest():
    with pytest.raises(UnauthorizedError):
        get_viewer_context(authorization=None, guest_session_id=None)


def test_api_token_dependency_accepts_active_token(db_session, user):
    _, token = auth_service.create_api_token(db_session, user.id, "Phone")
    assert (
        get_current_user_id_or_api_token(
            authorization=bearer_credentials(token), db=db_session
        )
        == user.id
    )
    [stored] = auth_service.list_api_tokens(db_session, user.id)
    assert stored.last_used_at is not None
    assert token not in (stored.token_hash, stored.token_hint)


def test_api_token_dependency_rejects_revoked_token(db_session, user):
    api_token, token = auth_service.create_api_token(db_session, user.id, "Phone")
    assert auth_service.revoke_api_token(db_session, user.id, api_token.id)

    with pytest.raises(UnauthorizedError):
        get_current_user_id_or_api_token(
            authorization=bearer_credentials(token), db=db_session
        )


def test_api_token_dependency_accepts_web_session_jwt(db_session):
    token = make_access_token(42)
    assert (
        get_current_user_id_or_api_token(
            authorization=bearer_credentials(token), db=db_session
        )
        == 42
    )


def test_legacy_long_term_jwt_is_checked_by_hash(db_session, user):
    """Migrated long-term tokens keep working, even if their JWT still decodes."""
    from src.auth.models import ApiToken

    token = make_long_term_token(user.id)
    with pytest.raises(UnauthorizedError):
        get_current_user_id_or_api_token(
            authorization=bearer_credentials(token), db=db_session
        )
    db_session.add(
        ApiToken(
            user_id=user.id,
            name="Legacy token",
            token_hash=auth_service.hash_api_token(token),
            token_hint=token[-4:],
        )
    )
    db_session.flush()
    assert (
        get_current_user_id_or_api_token(
            authorization=bearer_credentials(token), db=db_session
        )
        == user.id
    )


def test_api_token_dependency_rejects_invalid_token(db_session):
    with pytest.raises(UnauthorizedError):
        get_current_user_id_or_api_token(
            authorization=bearer_credentials("invalid-token"), db=db_session
        )
