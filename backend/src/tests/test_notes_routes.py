import pytest


async def register_and_login(client, email: str, password: str = "password123") -> str:
    register_response = await client.post(
        "/api/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Notes User",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v2/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200
    return login_response.json()["token"]


@pytest.mark.asyncio
async def test_notes_crud(client):
    token = await register_and_login(client, "notes@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    video_id = "abc123DEF45"
    create_response = await client.post(
        f"/api/v2/videos/{video_id}/notes",
        headers=headers,
        json={
            "timestamp": "01:23",
            "text": "First note",
            "video_title": "Test Video",
        },
    )
    assert create_response.status_code == 201
    created_note = create_response.json()
    assert created_note["video_id"] == video_id
    assert created_note["text"] == "First note"

    list_response = await client.get(
        f"/api/v2/videos/{video_id}/notes",
        headers=headers,
    )
    assert list_response.status_code == 200
    notes_payload = list_response.json()
    assert len(notes_payload) == 1
    assert notes_payload[0]["id"] == created_note["id"]

    patch_response = await client.patch(
        f"/api/v2/notes/{created_note['id']}",
        headers=headers,
        json={"text": "Updated note", "generated_by_ai": True},
    )
    assert patch_response.status_code == 200
    updated_note = patch_response.json()
    assert updated_note["text"] == "Updated note"
    assert updated_note["generated_by_ai"] is True

    delete_response = await client.delete(
        f"/api/v2/notes/{created_note['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Note deleted successfully"


@pytest.mark.asyncio
async def test_create_note_with_long_term_token(client):
    token = await register_and_login(client, "longterm@example.com")

    token_response = await client.post(
        "/api/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert token_response.status_code == 200
    long_term_token = token_response.json()["token"]

    create_response = await client.post(
        "/api/v2/videos/xyz987LMN12/notes",
        headers={"Authorization": f"Bearer {long_term_token}"},
        json={
            "timestamp": "00:45",
            "text": None,
            "video_title": "Long Term Video",
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["video_id"] == "xyz987LMN12"
    assert payload["text"] is None
