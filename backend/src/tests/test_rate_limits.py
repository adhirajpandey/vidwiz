import pytest

from src.config import settings
from src.shared.ratelimit import limiter


@pytest.mark.asyncio
async def test_auth_rate_limit_enforced(client):
    limiter.enabled = True
    settings.rate_limit_enabled = True

    headers = {"X-Forwarded-For": "203.0.113.10"}
    try:
        register_response = await client.post(
            "/v2/auth/register",
            json={
                "email": "limit@example.com",
                "password": "password123",
                "name": "Limit",
            },
            headers=headers,
        )
        assert register_response.status_code == 201

        for _ in range(10):
            login_response = await client.post(
                "/v2/auth/login",
                json={"email": "limit@example.com", "password": "password123"},
                headers=headers,
            )
            assert login_response.status_code == 200

        blocked_response = await client.post(
            "/v2/auth/login",
            json={"email": "limit@example.com", "password": "password123"},
            headers=headers,
        )
        assert blocked_response.status_code == 429
        payload = blocked_response.json()
        assert payload["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        limiter.enabled = False
        settings.rate_limit_enabled = False
