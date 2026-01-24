def test_wiz_init_rejects_playlist_url(client):
    response = client.post(
        "/api/wiz/init",
        json={
            "video_id": "https://www.youtube.com/watch?v=abcdefghijk&list=PL12345"
        },
    )

    assert response.status_code == 422
    data = response.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(
        detail["field"] == "video_id"
        and "playlist" in detail["message"].lower()
        for detail in data["error"]["details"]
    )


def test_wiz_init_rejects_invalid_video_id(client):
    response = client.post(
        "/api/wiz/init",
        json={"video_id": "not_a_valid_id"},
    )

    assert response.status_code == 422
    data = response.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(
        detail["field"] == "video_id"
        and "valid youtube video id" in detail["message"].lower()
        for detail in data["error"]["details"]
    )


def test_wiz_chat_rejects_invalid_video_id(client):
    response = client.post(
        "/api/wiz/chat",
        headers={"X-Guest-Session-ID": "guest_validation"},
        json={"video_id": "invalid", "message": "hello"},
    )

    assert response.status_code == 422
    data = response.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(
        detail["field"] == "video_id"
        and "valid youtube video id" in detail["message"].lower()
        for detail in data["error"]["details"]
    )
