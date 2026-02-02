import pytest

from src.conversations import service as conversations_service


@pytest.mark.asyncio
async def test_create_and_get_conversation_with_guest(client):
    headers = {"X-Guest-Session-ID": "guest-123"}
    video_id = "abc123DEF45"

    create_response = await client.post(
        "/api/v2/conversations",
        headers=headers,
        json={"video_id": video_id},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["video_id"] == video_id

    conversation_id = payload["id"]
    get_response = await client.get(
        f"/api/v2/conversations/{conversation_id}",
        headers=headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == conversation_id


@pytest.mark.asyncio
async def test_conversation_access_scoped_to_guest(client):
    video_id = "xyz987LMN12"
    guest_a = {"X-Guest-Session-ID": "guest-a"}
    guest_b = {"X-Guest-Session-ID": "guest-b"}

    create_response = await client.post(
        "/api/v2/conversations",
        headers=guest_a,
        json={"video_id": video_id},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    forbidden_response = await client.get(
        f"/api/v2/conversations/{conversation_id}",
        headers=guest_b,
    )
    assert forbidden_response.status_code == 404


@pytest.mark.asyncio
async def test_list_conversation_messages(client, db_session):
    guest_id = "guest-list"
    headers = {"X-Guest-Session-ID": guest_id}
    video_id = "mno456PQR78"

    conversations_service.get_or_create_video(db_session, video_id)
    conversation = conversations_service.create_conversation(
        db_session, video_id, None, guest_id
    )

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
        f"/api/v2/conversations/{conversation.id}/messages",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["role"] == "user"
    assert payload[1]["role"] == "assistant"
