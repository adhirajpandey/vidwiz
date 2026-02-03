import pytest


async def register_and_login(client, email: str, password: str = "password123") -> str:
    register_response = await client.post(
        "/v2/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Notes User",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/v2/auth/login",
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
        f"/v2/videos/{video_id}/notes",
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
        f"/v2/videos/{video_id}/notes",
        headers=headers,
    )
    assert list_response.status_code == 200
    notes_payload = list_response.json()
    assert len(notes_payload) == 1
    assert notes_payload[0]["id"] == created_note["id"]

    patch_response = await client.patch(
        f"/v2/notes/{created_note['id']}",
        headers=headers,
        json={"text": "Updated note", "generated_by_ai": True},
    )
    assert patch_response.status_code == 200
    updated_note = patch_response.json()
    assert updated_note["text"] == "Updated note"
    assert updated_note["generated_by_ai"] is True

    delete_response = await client.delete(
        f"/v2/notes/{created_note['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Note deleted successfully"


@pytest.mark.asyncio
async def test_create_note_with_long_term_token(client):
    token = await register_and_login(client, "longterm@example.com")

    token_response = await client.post(
        "/v2/auth/tokens",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert token_response.status_code == 200
    long_term_token = token_response.json()["token"]

    create_response = await client.post(
        "/v2/videos/xyz987LMN12/notes",
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


@pytest.mark.asyncio
async def test_list_notes_requires_auth(client):
    response = await client.get("/v2/videos/abc123DEF45/notes")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_note_rejects_invalid_timestamp(client):
    token = await register_and_login(client, "invalid-ts@example.com")
    response = await client.post(
        "/v2/videos/abc123DEF45/notes",
        headers={"Authorization": f"Bearer {token}"},
        json={"timestamp": "bad", "text": "note", "video_title": "Test"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_update_note_requires_payload_fields(client):
    token = await register_and_login(client, "update-empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/v2/videos/abc123DEF45/notes",
        headers=headers,
        json={"timestamp": "00:01", "text": "note"},
    )
    note_id = create_response.json()["id"]

    response = await client.patch(
        f"/v2/notes/{note_id}",
        headers=headers,
        json={},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "BAD_REQUEST"
    assert payload["error"]["message"] == "No fields provided for update"


@pytest.mark.asyncio
async def test_update_note_rejects_extra_fields(client):
    token = await register_and_login(client, "update-extra@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/v2/videos/abc123DEF45/notes",
        headers=headers,
        json={"timestamp": "00:01", "text": "note"},
    )
    note_id = create_response.json()["id"]

    response = await client.patch(
        f"/v2/notes/{note_id}",
        headers=headers,
        json={"text": "updated", "extra": "nope"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_delete_note_not_found(client):
    token = await register_and_login(client, "delete-missing@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete("/v2/notes/9999", headers=headers)
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
