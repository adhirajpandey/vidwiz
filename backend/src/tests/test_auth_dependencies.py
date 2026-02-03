from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.auth import service as auth_service
from src.auth.dependencies import (
    get_current_user_id,
    get_current_user_id_or_long_term,
    get_viewer_context,
)
from src.config import settings
from src.exceptions import UnauthorizedError


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
    assert get_current_user_id(f"Bearer {token}") == 42


def test_get_current_user_id_rejects_long_term_token():
    token = make_long_term_token(42)
    with pytest.raises(UnauthorizedError):
        get_current_user_id(f"Bearer {token}")


def test_get_current_user_id_rejects_invalid_header():
    with pytest.raises(UnauthorizedError):
        get_current_user_id("Token abc123")


def test_get_current_user_id_rejects_invalid_payload():
    token = jwt.encode(
        {"email": "missing@example.com"},
        settings.secret_key,
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        get_current_user_id(f"Bearer {token}")


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
        get_current_user_id(f"Bearer {token}")


def test_get_current_user_id_rejects_missing_header():
    with pytest.raises(UnauthorizedError):
        get_current_user_id(None)


def test_get_viewer_context_prefers_auth():
    token = make_access_token(7)
    context = get_viewer_context(
        authorization=f"Bearer {token}",
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


def test_get_current_user_id_or_long_term_accepts_active_token(db_session):
    user = auth_service.create_user(
        db_session,
        "lt@example.com",
        "LT User",
        "password123",
    )
    token = auth_service.create_long_term_token(db_session, user, settings.secret_key)
    assert (
        get_current_user_id_or_long_term(
            authorization=f"Bearer {token}",
            db=db_session,
        )
        == user.id
    )


def test_get_current_user_id_or_long_term_rejects_revoked_token(db_session):
    user = auth_service.create_user(
        db_session,
        "lt-revoke@example.com",
        "LT Revoke",
        "password123",
    )
    token = auth_service.create_long_term_token(db_session, user, settings.secret_key)
    auth_service.revoke_long_term_token(db_session, user)

    with pytest.raises(UnauthorizedError):
        get_current_user_id_or_long_term(
            authorization=f"Bearer {token}",
            db=db_session,
        )


def test_get_current_user_id_or_long_term_rejects_invalid_token(db_session):
    with pytest.raises(UnauthorizedError):
        get_current_user_id_or_long_term(
            authorization="Bearer invalid-token",
            db=db_session,
        )
