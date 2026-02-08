import jwt

from src.auth import service as auth_service
from src.auth.models import User
from src.config import settings


def test_create_and_find_user(db_session):
    user = auth_service.create_user(
        db_session,
        "create@example.com",
        "Create User",
        "password123",
    )
    assert user.id is not None
    assert user.email == "create@example.com"
    assert user.password_hash is not None
    assert user.password_hash != "password123"

    found = auth_service.find_user_by_email(db_session, "create@example.com")
    assert found is not None
    assert found.id == user.id


def test_authenticate_user_success_and_failure(db_session):
    auth_service.create_user(
        db_session,
        "auth@example.com",
        "Auth User",
        "password123",
    )

    assert (
        auth_service.authenticate_user(
            db_session,
            "auth@example.com",
            "password123",
        )
        is not None
    )
    assert (
        auth_service.authenticate_user(
            db_session,
            "auth@example.com",
            "wrong",
        )
        is None
    )


def test_generate_jwt_token_payload(db_session):
    user = User(
        email="token@example.com",
        name="Token User",
        profile_image_url="https://example.com/avatar.png",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = auth_service.generate_jwt_token(user, settings.secret_key, 1)
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["user_id"] == user.id
    assert payload["email"] == "token@example.com"
    assert payload["name"] == "Token User"
    assert payload["profile_image_url"] == "https://example.com/avatar.png"


def test_get_user_by_long_term_token(db_session):
    user = auth_service.create_user(
        db_session,
        "lookup@example.com",
        "Lookup User",
        "password123",
    )
    token = auth_service.create_long_term_token(db_session, user, settings.secret_key)
    found = auth_service.get_user_by_long_term_token(db_session, token)
    assert found is not None
    assert found.id == user.id


def test_long_term_token_create_and_revoke(db_session):
    user = auth_service.create_user(
        db_session,
        "longterm@example.com",
        "Long Term",
        "password123",
    )
    token = auth_service.create_long_term_token(db_session, user, settings.secret_key)
    assert token
    refreshed = auth_service.get_user_by_id(db_session, user.id)
    assert refreshed.long_term_token == token

    auth_service.revoke_long_term_token(db_session, refreshed)
    revoked = auth_service.get_user_by_id(db_session, user.id)
    assert revoked.long_term_token is None


def test_build_profile_data_includes_long_term_token(db_session):
    user = auth_service.create_user(
        db_session,
        "token-profile@example.com",
        "Token Profile",
        "password123",
    )
    token = auth_service.create_long_term_token(db_session, user, settings.secret_key)
    data = auth_service.build_profile_data(user, include_long_term_token=True)
    assert data["token_exists"] is True
    assert data["long_term_token"] == token


def test_build_profile_data_flags(db_session):
    user = User(
        email="profile@example.com",
        name="Profile",
        profile_data={"ai_notes_enabled": True},
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    data = auth_service.build_profile_data(user, include_long_term_token=False)
    assert data["ai_notes_enabled"] is True
    assert data["token_exists"] is False
    assert "long_term_token" not in data


def test_update_profile_updates_fields(db_session):
    user = User(
        email="update@example.com",
        name="Before",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    updated = auth_service.update_profile(
        db_session,
        user,
        name="After",
        ai_notes_enabled=True,
    )
    assert updated.name == "After"
    assert updated.profile_data["ai_notes_enabled"] is True


def test_upsert_google_user_links_existing_by_email(db_session):
    existing = auth_service.create_user(
        db_session,
        "google-link@example.com",
        "Existing User",
        "password123",
    )
    user = auth_service.upsert_google_user(
        db_session,
        "google-123",
        "google-link@example.com",
        "Google User",
        "https://example.com/avatar.png",
    )
    assert user.id == existing.id
    assert user.google_id == "google-123"
    assert user.profile_image_url == "https://example.com/avatar.png"


def test_upsert_google_user_updates_missing_name(db_session):
    user = auth_service.upsert_google_user(
        db_session,
        "google-456",
        "google-name@example.com",
        "Google Name",
        None,
    )
    assert user.name == "Google Name"
