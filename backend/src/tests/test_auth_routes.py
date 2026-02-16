import jwt
import pytest

from src.config import settings


async def register_user(
    client,
    email: str,
    password: str = "password123",
    name: str = "Test User",
):
    return await client.post(
        "/v2/auth/register",
        json={"email": email, "password": password, "name": name},
    )


async def login_user(client, email: str, password: str = "password123"):
    return await client.post(
        "/v2/auth/login",
        json={"email": email, "password": password},
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


@pytest.mark.asyncio
async def test_register_and_login(client):
    register_response = await register_user(client, "test@example.com")
    assert register_response.status_code == 201
    assert register_response.json()["message"] == "User created successfully"

    login_response = await login_user(client, "test@example.com")
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    payload = decode_token(token)
    assert payload["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_signup_grants_credits(client):
    await register_user(client, "credits@example.com")
    login_response = await login_user(client, "credits@example.com")
    token = login_response.json()["token"]

    profile_response = await client.get(
        "/v2/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_response.status_code == 200
    payload = profile_response.json()
    assert payload["credits_balance"] == 100
    assert payload["ai_notes_enabled"] is True


@pytest.mark.asyncio
async def test_register_normalizes_email_and_name(client):
    register_response = await register_user(
        client,
        "  Mixed@Example.com ",
        name="  Mixed User  ",
    )
    assert register_response.status_code == 201

    login_response = await login_user(client, "mixed@example.com")
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_register_rejects_invalid_payload(client):
    response = await register_user(
        client,
        "bad-email",
        password="short",
        name=" ",
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "Request validation failed"


@pytest.mark.asyncio
async def test_register_conflict_on_duplicate_email(client):
    await register_user(client, "dupe@example.com")
    response = await register_user(client, "DUPE@example.com")
    assert response.status_code == 409
    payload = response.json()
    assert payload["error"]["code"] == "CONFLICT"
    assert payload["error"]["message"] == "Email already exists"


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(client):
    await register_user(client, "login@example.com")
    response = await login_user(client, "login@example.com", password="wrong")
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"
    assert payload["error"]["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_requires_secret_key(client, monkeypatch):
    await register_user(client, "secret@example.com")
    monkeypatch.setattr(settings, "secret_key", None, raising=False)
    response = await login_user(client, "secret@example.com")
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["message"] == "SECRET_KEY is not configured"


@pytest.mark.asyncio
async def test_login_rejects_missing_password(client):
    response = await client.post(
        "/v2/auth/login",
        json={"email": "missing@example.com"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_google_login_success(client, monkeypatch):
    from src.auth import service as auth_service

    def mock_verify_google_token(_credential: str, _client_id: str):
        return {
            "sub": "google-123",
            "email": "google@example.com",
            "name": "Google User",
            "picture": "https://example.com/avatar.png",
        }

    monkeypatch.setattr(auth_service, "verify_google_token", mock_verify_google_token)
    response = await client.post(
        "/v2/auth/google",
        json={"credential": "valid-token"},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    payload = decode_token(token)
    assert payload["email"] == "google@example.com"
    assert payload["name"] == "Google User"


@pytest.mark.asyncio
async def test_google_login_requires_config(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", None, raising=False)
    response = await client.post(
        "/v2/auth/google",
        json={"credential": "valid-token"},
    )
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["message"] == "Google OAuth not configured"


@pytest.mark.asyncio
async def test_google_login_requires_secret_key(client, monkeypatch):
    from src.auth import service as auth_service

    def mock_verify_google_token(_credential: str, _client_id: str):
        return {
            "sub": "google-789",
            "email": "google-secret@example.com",
            "name": "Google Secret",
        }

    monkeypatch.setattr(auth_service, "verify_google_token", mock_verify_google_token)
    monkeypatch.setattr(settings, "secret_key", None, raising=False)
    response = await client.post(
        "/v2/auth/google",
        json={"credential": "valid-token"},
    )
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["message"] == "SECRET_KEY is not configured"


@pytest.mark.asyncio
async def test_google_login_requires_email(client, monkeypatch):
    from src.auth import service as auth_service

    def mock_verify_google_token(_credential: str, _client_id: str):
        return {"sub": "google-456"}

    monkeypatch.setattr(auth_service, "verify_google_token", mock_verify_google_token)
    response = await client.post(
        "/v2/auth/google",
        json={"credential": "valid-token"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "BAD_REQUEST"
    assert payload["error"]["message"] == "Email is required for Google Sign-In"


@pytest.mark.asyncio
async def test_google_login_invalid_credential(client, monkeypatch):
    from src.auth import service as auth_service

    def mock_verify_google_token(_credential: str, _client_id: str):
        raise ValueError("Invalid")

    monkeypatch.setattr(auth_service, "verify_google_token", mock_verify_google_token)
    response = await client.post(
        "/v2/auth/google",
        json={"credential": "bad-token"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"
    assert payload["error"]["message"] == "Invalid Google credential"


@pytest.mark.asyncio
async def test_profile_and_long_term_token_flow(client):
    await register_user(
        client,
        "profile@example.com",
        name="Profile User",
    )
    login_response = await login_user(client, "profile@example.com")
    token = login_response.json()["token"]

    token_response = await client.post(
        "/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert token_response.status_code == 200
    assert "token" in token_response.json()

    profile_response = await client.get(
        "/v2/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    profile_payload = profile_response.json()
    assert profile_payload["email"] == "profile@example.com"
    assert profile_payload["token_exists"] is True
    assert profile_payload["long_term_token"] is not None

    patch_response = await client.patch(
        "/v2/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"ai_notes_enabled": True, "name": "Updated Name"},
    )

    assert patch_response.status_code == 200
    updated_payload = patch_response.json()
    assert updated_payload["name"] == "Updated Name"
    assert updated_payload["ai_notes_enabled"] is True


@pytest.mark.asyncio
async def test_profile_rejects_long_term_token(client):
    await register_user(client, "longterm-profile@example.com")
    login_response = await login_user(client, "longterm-profile@example.com")
    token = login_response.json()["token"]

    token_response = await client.post(
        "/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    long_term_token = token_response.json()["token"]

    profile_response = await client.get(
        "/v2/users/me",
        headers={"Authorization": f"Bearer {long_term_token}"},
    )
    assert profile_response.status_code == 401
    payload = profile_response.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"
    assert (
        payload["error"]["message"]
        == "Long-term tokens are not allowed for this endpoint"
    )


@pytest.mark.asyncio
async def test_profile_requires_auth(client):
    response = await client.get("/v2/users/me")
    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "UNAUTHORIZED"
    assert payload["error"]["message"] == "Missing or invalid Authorization header"


@pytest.mark.asyncio
async def test_update_profile_validates_name(client):
    await register_user(client, "profile-update@example.com")
    login_response = await login_user(client, "profile-update@example.com")
    token = login_response.json()["token"]

    response = await client.patch(
        "/v2/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "x"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_long_term_token_errors(client):
    await register_user(client, "token-errors@example.com")
    login_response = await login_user(client, "token-errors@example.com")
    token = login_response.json()["token"]

    token_response = await client.post(
        "/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert token_response.status_code == 200

    duplicate_response = await client.post(
        "/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert duplicate_response.status_code == 400
    payload = duplicate_response.json()
    assert payload["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_long_term_token_missing_user(client):
    token = jwt.encode(
        {
            "user_id": 9999,
            "email": "ghost@example.com",
            "name": "Ghost",
        },
        settings.secret_key,
        algorithm="HS256",
    )
    response = await client.post(
        "/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_revoke_long_term_token_requires_existing_token(client):
    await register_user(client, "revoke@example.com")
    login_response = await login_user(client, "revoke@example.com")
    token = login_response.json()["token"]

    response = await client.delete(
        "/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
