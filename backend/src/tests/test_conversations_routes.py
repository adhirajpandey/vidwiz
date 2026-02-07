import pytest

from src.auth import service as auth_service
from src.config import settings
from src.conversations import service as conversations_service
from src.conversations.models import Conversation


def guest_headers(guest_session_id: str) -> dict[str, str]:
    return {"X-Guest-Session-ID": guest_session_id}


@pytest.mark.asyncio
async def test_create_conversation_requires_auth_or_guest(client):
    response = await client.post(
        "/v2/conversations",
        json={"video_id": "abc123DEF45"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_and_get_conversation_as_guest(client, db_session):
    headers = guest_headers("guest-123")
    create_response = await client.post(
        "/v2/conversations",
        headers=headers,
        json={"video_id": "abc123DEF45"},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["video_id"] == "abc123DEF45"

    created = db_session.get(Conversation, payload["id"])
    assert created is not None
    assert created.guest_session_id == "guest-123"

    get_response = await client.get(
        f"/v2/conversations/{payload['id']}",
        headers=headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["video_id"] == "abc123DEF45"


@pytest.mark.asyncio
async def test_create_conversation_blocks_when_insufficient_credits(
    client, db_session
):
    user = auth_service.create_user(
        db_session, "credits-low@example.com", "Credits Low", "password123"
    )
    user.credits_balance = 4
    db_session.commit()

    token = auth_service.generate_jwt_token(user, settings.secret_key, 1)
    response = await client.post(
        "/v2/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"video_id": "abc123DEF45"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "FORBIDDEN"
    assert payload["error"]["message"] == "Insufficient credits"


@pytest.mark.asyncio
async def test_create_conversation_charges_once_per_video(client, db_session):
    user = auth_service.create_user(
        db_session, "credits-ok@example.com", "Credits Ok", "password123"
    )
    user.credits_balance = 10
    db_session.commit()

    token = auth_service.generate_jwt_token(user, settings.secret_key, 1)
    response_one = await client.post(
        "/v2/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"video_id": "abc123DEF45"},
    )
    assert response_one.status_code == 201

    response_two = await client.post(
        "/v2/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"video_id": "abc123DEF45"},
    )
    assert response_two.status_code == 201

    refreshed = auth_service.get_user_by_id(db_session, user.id)
    assert refreshed.credits_balance == 5


@pytest.mark.asyncio
async def test_create_conversation_rejects_invalid_video_id(client):
    response = await client.post(
        "/v2/conversations",
        headers=guest_headers("guest-invalid"),
        json={"video_id": "bad"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_get_conversation_scoped_by_guest(client, db_session):
    conversation = Conversation(video_id="abc123DEF45", guest_session_id="guest-123")
    db_session.add(conversation)
    db_session.commit()

    response = await client.get(
        f"/v2/conversations/{conversation.id}",
        headers=guest_headers("guest-456"),
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["message"] == "Conversation not found"


@pytest.mark.asyncio
async def test_list_messages(client, db_session):
    conversation = Conversation(video_id="abc123DEF45", guest_session_id="guest-321")
    db_session.add(conversation)
    db_session.commit()

    conversations_service.save_chat_message(
        db_session,
        conversation.id,
        conversations_service.DB_ROLE_USER,
        "Hello",
    )
    conversations_service.save_chat_message(
        db_session,
        conversation.id,
        conversations_service.DB_ROLE_ASSISTANT,
        "Hi there",
    )

    response = await client.get(
        f"/v2/conversations/{conversation.id}/messages",
        headers=guest_headers("guest-321"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert [message["content"] for message in payload] == ["Hello", "Hi there"]


@pytest.mark.asyncio
async def test_create_message_returns_processing_when_transcript_missing(
    client, db_session, monkeypatch
):
    conversation = Conversation(video_id="abc123DEF45", guest_session_id="guest-777")
    db_session.add(conversation)
    db_session.commit()

    def fake_prepare_chat(_db, _conversation, _viewer, _message):
        return None, None, [], None

    monkeypatch.setattr(conversations_service, "prepare_chat", fake_prepare_chat)

    response = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=guest_headers("guest-777"),
        json={"message": "Hello"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "processing"
    assert payload["message"] == "Transcript processing"


@pytest.mark.asyncio
async def test_create_message_rejects_empty_message(client, db_session):
    conversation = Conversation(video_id="abc123DEF45", guest_session_id="guest-999")
    db_session.add(conversation)
    db_session.commit()

    response = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=guest_headers("guest-999"),
        json={"message": "   "},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
