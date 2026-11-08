import json
import logging
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth import service as auth_service
from src.credits import service as credits_service
from src.logging import (
    JsonFormatter,
    LokiPathFilter,
    RequestAuth,
    hash_guest_id,
    request_auth_var,
)
from src.main import create_app


def _find_request_log(caplog, path: str):
    for record in caplog.records:
        if getattr(record, "http_path", None) == path:
            return record
    return None


def _find_event(caplog, event: str):
    for record in caplog.records:
        if getattr(record, "event", None) == event:
            return record
    return None


async def _register(client, email: str, password: str = "secret123") -> None:
    await client.post(
        "/v2/auth/register",
        json={"email": email, "password": password, "name": "Test User"},
    )


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
async def test_failed_request_body_redacts_credentials(client, caplog):
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        response = await client.post(
            "/v2/payments/checkout",
            json={"password": "supersecret", "credential": "google-id-token"},
        )

    assert response.status_code >= 400
    record = _find_request_log(caplog, "/v2/payments/checkout")
    assert record is not None
    body = json.loads(record.request_body)
    assert body["password"] == "***"
    assert body["credential"] == "***"
    assert record.response_body is not None


@pytest.mark.asyncio
async def test_failed_request_body_truncation(client, caplog):
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        await client.post("/v2/payments/checkout", json={"data": "a" * 10000})

    record = _find_request_log(caplog, "/v2/payments/checkout")
    assert record is not None
    assert record.request_body_truncated is True
    assert record.request_body is not None


@pytest.mark.asyncio
async def test_successful_request_logs_no_bodies(client, caplog):
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        response = await client.get("/v2/payments/products")

    assert response.status_code == 200
    record = _find_request_log(caplog, "/v2/payments/products")
    assert record is not None
    assert record.request_body is None
    assert record.response_body is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/v2/auth/login", {"email": "x@example.com", "password": "wrong-pass"}),
        ("/v2/conversations", {"video_id": "private chat text"}),
        ("/v2/captures", {"note": "private note text"}),
        ("/v2/internal/tasks/1/result", {"transcript": "private transcript"}),
    ],
)
async def test_sensitive_routes_never_log_bodies_on_failure(
    client, caplog, path, payload
):
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        response = await client.post(path, json=payload)

    assert response.status_code >= 400
    record = _find_request_log(caplog, path)
    assert record is not None
    assert record.request_body is None
    assert record.response_body is None


@pytest.mark.asyncio
async def test_failed_google_sign_in_logs_reason_without_credential(
    client, caplog, monkeypatch
):
    def reject_credential(credential, client_id):
        raise ValueError("bad token")

    monkeypatch.setattr(auth_service, "verify_google_token", reject_credential)

    with caplog.at_level(logging.INFO):
        response = await client.post(
            "/v2/auth/google", json={"credential": "not-a-google-token"}
        )

    assert response.status_code == 401
    record = _find_request_log(caplog, "/v2/auth/google")
    assert record.request_body is None
    assert "not-a-google-token" not in JsonFormatter().format(record)
    assert _find_event(caplog, "auth.login_failed").reason == "invalid_credential"


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
    assert record.auth_kind == "jwt"
    assert isinstance(record.user_id, int)
    assert record.http_route == "/v2/users/me"
    assert not hasattr(record, "user_email")


@pytest.mark.asyncio
async def test_request_without_credential_is_anonymous(client, caplog):
    with caplog.at_level(logging.INFO):
        response = await client.get("/v2/users/me")

    assert response.status_code == 401
    record = _find_request_log(caplog, "/v2/users/me")
    assert record.auth_kind == "anonymous"
    assert record.user_id is None
    assert _find_event(caplog, "auth.session_rejected") is None


@pytest.mark.asyncio
async def test_rejected_token_is_logged(client, caplog):
    with caplog.at_level(logging.INFO):
        response = await client.get(
            "/v2/users/me", headers={"Authorization": "Bearer not-a-jwt"}
        )

    assert response.status_code == 401
    assert _find_request_log(caplog, "/v2/users/me").auth_kind == "invalid_token"
    assert _find_event(caplog, "auth.session_rejected").reason == "invalid"


@pytest.mark.asyncio
async def test_guest_request_logs_hash_and_not_raw_id(client, caplog):
    path = "/v2/videos/aaaaaaaaaaa"
    with caplog.at_level(logging.INFO):
        await client.get(path, headers={"X-Guest-Session-ID": "guest-raw-id"})

    record = _find_request_log(caplog, path)
    assert record.auth_kind == "guest"
    assert record.guest_id_hash == hash_guest_id("guest-raw-id")
    assert "guest-raw-id" not in JsonFormatter().format(record)


@pytest.mark.asyncio
async def test_rejected_token_continuing_as_guest_keeps_both_signals(client, caplog):
    path = "/v2/videos/aaaaaaaaaaa"
    with caplog.at_level(logging.INFO):
        await client.get(
            path,
            headers={
                "Authorization": "Bearer not-a-jwt",
                "X-Guest-Session-ID": "guest-raw-id",
            },
        )

    record = _find_request_log(caplog, path)
    assert record.auth_kind == "invalid_token"
    assert record.guest_id_hash == hash_guest_id("guest-raw-id")


def test_api_token_use_is_recorded(db_session):
    user = auth_service.create_user(
        db_session, f"apitoken-{uuid4().hex}@example.com", "Test User", "secret123"
    )
    api_token, raw_token = auth_service.create_api_token(db_session, user.id, "phone")
    auth = RequestAuth()
    context_token = request_auth_var.set(auth)
    try:
        auth_service.authenticate_api_token(db_session, raw_token)
    finally:
        request_auth_var.reset(context_token)

    assert auth.kind == "api_token"
    assert auth.user_id == user.id
    assert auth.api_token_id == api_token.id


@pytest.mark.asyncio
async def test_failed_login_logs_reason_and_user_without_email(client, caplog):
    email = f"wrongpass-{uuid4().hex}@example.com"
    await _register(client, email)

    with caplog.at_level(logging.INFO):
        await client.post(
            "/v2/auth/login", json={"email": email, "password": "wrong-password"}
        )

    record = _find_event(caplog, "auth.login_failed")
    assert record.reason == "wrong_password"
    assert isinstance(record.user_id, int)
    assert email not in JsonFormatter().format(record)


@pytest.mark.asyncio
async def test_failed_login_with_unknown_email_has_no_identity(client, caplog):
    email = f"unknown-{uuid4().hex}@example.com"
    with caplog.at_level(logging.INFO):
        await client.post(
            "/v2/auth/login", json={"email": email, "password": "secret123"}
        )

    record = _find_event(caplog, "auth.login_failed")
    assert record.reason == "unknown_email"
    assert not hasattr(record, "user_id")
    assert email not in JsonFormatter().format(record)


@pytest.mark.asyncio
async def test_duplicate_registration_logs_existing_user(client, caplog):
    email = f"duplicate-{uuid4().hex}@example.com"
    await _register(client, email)

    with caplog.at_level(logging.INFO):
        response = await client.post(
            "/v2/auth/register",
            json={"email": email, "password": "secret123", "name": "Test User"},
        )

    assert response.status_code == 409
    record = _find_event(caplog, "auth.registration_failed")
    assert record.reason == "email_exists"
    assert isinstance(record.user_id, int)


@pytest.mark.asyncio
async def test_login_event_links_guest_session(client, caplog):
    email = f"guestlink-{uuid4().hex}@example.com"
    await _register(client, email)

    with caplog.at_level(logging.INFO):
        await client.post(
            "/v2/auth/login",
            json={"email": email, "password": "secret123"},
            headers={"X-Guest-Session-ID": "guest-raw-id"},
        )

    record = _find_event(caplog, "auth.login_succeeded")
    assert record.method == "password"
    assert isinstance(record.user_id, int)
    assert record.guest_id_hash == hash_guest_id("guest-raw-id")


def test_credit_charge_is_logged_once(db_session, caplog):
    user = auth_service.create_user(
        db_session, f"charge-{uuid4().hex}@example.com", "Test User", "secret123"
    )

    with caplog.at_level(logging.INFO):
        credits_service.charge_ai_moment(db_session, user.id, 12345)
        credits_service.charge_ai_moment(db_session, user.id, 12345)

    events = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "credits.charged"
    ]
    assert len(events) == 1
    assert events[0].user_id == user.id
    assert events[0].ref_id == "12345"


def test_health_is_excluded_from_loki():
    record = logging.LogRecord("vidwiz.api", logging.INFO, __file__, 1, "ok", (), None)
    record.http_path = "/health"
    assert LokiPathFilter().filter(record) is False


def test_json_formatter_puts_identity_fields_at_top_level():
    record = logging.LogRecord("vidwiz.api", logging.INFO, __file__, 1, "ok", (), None)
    record.event = "capture.created"
    record.auth_kind = "guest"
    record.guest_id_hash = "abc123"
    record.api_token_id = 7
    record.http_route = "/v2/users/me"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "capture.created"
    assert payload["auth_kind"] == "guest"
    assert payload["guest_id_hash"] == "abc123"
    assert payload["api_token_id"] == 7
    assert payload["http_route"] == "/v2/users/me"
    assert "extra" not in payload


@pytest.mark.asyncio
async def test_request_logs_client_ip_from_cloudflare_header_first(client, caplog):
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        await client.get(
            "/v2/payments/products",
            headers={
                "CF-Connecting-IP": "192.0.2.50",
                "X-Forwarded-For": "203.0.113.10, 198.51.100.7",
            },
        )

    record = _find_request_log(caplog, "/v2/payments/products")
    assert record.client_ip == "192.0.2.50"


@pytest.mark.asyncio
async def test_request_logs_client_ip_from_forwarded_headers(client, caplog):
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        await client.get(
            "/v2/payments/products",
            headers={
                "X-Forwarded-For": "203.0.113.10, 198.51.100.7",
                "X-Real-IP": "198.51.100.8",
            },
        )

    record = _find_request_log(caplog, "/v2/payments/products")
    assert record is not None
    assert record.client_ip == "203.0.113.10"


@pytest.mark.asyncio
async def test_request_logs_client_ip_from_real_ip_when_forwarded_for_missing(
    client, caplog
):
    with caplog.at_level(logging.INFO, logger="vidwiz.api"):
        await client.get(
            "/v2/payments/products",
            headers={"X-Real-IP": "198.51.100.8"},
        )

    record = _find_request_log(caplog, "/v2/payments/products")
    assert record is not None
    assert record.client_ip == "198.51.100.8"


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
