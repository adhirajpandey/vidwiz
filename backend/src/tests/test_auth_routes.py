import jwt
import pytest

from src.config import settings


@pytest.mark.asyncio
async def test_register_and_login(client):
    register_response = await client.post(
        "/api/v2/auth/register",
        json={
            "email": "test@example.com",
            "password": "password123",
            "name": "Test User",
        },
    )

    assert register_response.status_code == 201
    assert register_response.json()["message"] == "User created successfully"

    login_response = await client.post(
        "/api/v2/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert login_response.status_code == 200
    token = login_response.json()["token"]
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert payload["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_profile_and_long_term_token_flow(client):
    await client.post(
        "/api/v2/auth/register",
        json={
            "email": "profile@example.com",
            "password": "password123",
            "name": "Profile User",
        },
    )

    login_response = await client.post(
        "/api/v2/auth/login",
        json={
            "email": "profile@example.com",
            "password": "password123",
        },
    )
    token = login_response.json()["token"]

    token_response = await client.post(
        "/api/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert token_response.status_code == 200
    assert "token" in token_response.json()

    profile_response = await client.get(
        "/api/v2/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    profile_payload = profile_response.json()
    assert profile_payload["email"] == "profile@example.com"
    assert profile_payload["token_exists"] is True
    assert profile_payload["long_term_token"] is not None

    patch_response = await client.patch(
        "/api/v2/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"ai_notes_enabled": True, "name": "Updated Name"},
    )

    assert patch_response.status_code == 200
    updated_payload = patch_response.json()
    assert updated_payload["name"] == "Updated Name"
    assert updated_payload["ai_notes_enabled"] is True
