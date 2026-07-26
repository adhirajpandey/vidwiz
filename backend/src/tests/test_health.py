import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cors_exposes_diagnostic_response_headers(client):
    response = await client.get(
        "/health",
        headers={"Origin": "https://vidwiz.online"},
    )

    exposed_headers = response.headers.get("access-control-expose-headers", "")
    assert "X-Request-ID" in exposed_headers
    assert "Retry-After" in exposed_headers
