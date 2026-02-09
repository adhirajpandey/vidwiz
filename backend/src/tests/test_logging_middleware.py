import json
import logging
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


def _find_request_log(caplog, path: str):
    for record in caplog.records:
        if getattr(record, "http_path", None) == path:
            return record
    return None


@pytest.mark.asyncio
async def test_request_id_added(client):
    email = f"reqid-{uuid4().hex}@example.com"
    response = await client.post(
        "/v2/auth/register",
        json={"email": email, "password": "secret123"},
    )
    assert response.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_request_id_passthrough(client):
    email = f"reqid-pass-{uuid4().hex}@example.com"
    response = await client.post(
        "/v2/auth/register",
        json={"email": email, "password": "secret123"},
        headers={"X-Request-ID": "test-123"},
    )
    assert response.headers.get("x-request-id") == "test-123"


@pytest.mark.asyncio
async def test_request_body_redaction(client, caplog):
    email = f"redact-{uuid4().hex}@example.com"
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        await client.post(
            "/v2/auth/register",
            json={"email": email, "password": "supersecret"},
        )

    record = _find_request_log(caplog, "/v2/auth/register")
    assert record is not None
    body = json.loads(record.request_body)
    assert body["password"] == "***"


@pytest.mark.asyncio
async def test_request_body_truncation(client, caplog):
    email = f"truncate-{uuid4().hex}@example.com"
    payload = {"email": email, "password": "secret123", "data": "a" * 10000}
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        await client.post("/v2/auth/register", json=payload)

    record = _find_request_log(caplog, "/v2/auth/register")
    assert record is not None
    assert record.request_body_truncated is True
    assert record.request_body is not None


@pytest.mark.asyncio
async def test_request_logs_user_fields(client, caplog):
    email = f"userfields-{uuid4().hex}@example.com"
    password = "secret123"
    await client.post(
        "/v2/auth/register",
        json={"email": email, "password": password, "name": "Test User"},
    )
    login_response = await client.post(
        "/v2/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["token"]

    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        await client.get(
            "/v2/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    record = _find_request_log(caplog, "/v2/users/me")
    assert record is not None
    assert record.user_email == email
    assert isinstance(record.user_id, int)


@pytest.mark.asyncio
async def test_status_level_mapping(caplog):
    app = create_app()

    @app.get("/_test_500")
    async def _test_500():
        raise RuntimeError("boom")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with caplog.at_level(logging.INFO, logger="vidwiz.api"):
            response = await client.get("/_test_500")

    assert response.status_code == 500
    record = _find_request_log(caplog, "/_test_500")
    assert record is not None
    assert record.levelname == "ERROR"
