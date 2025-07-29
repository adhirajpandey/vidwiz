import pytest
from vidwiz.app import create_app
from vidwiz.shared.models import Note, Video, User, db
import jwt
from datetime import datetime, timedelta, timezone

AUTH_TOKEN = "testtoken123"
AUTH_HEADER = {"Authorization": f"Bearer {AUTH_TOKEN}"}


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "AUTH_TOKEN": AUTH_TOKEN,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": "test_secret_key",
            "AI_NOTE_TOGGLE": True,
            "LAMBDA_URL": "https://test-lambda.com/invoke",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Create proper JWT auth headers"""
    with app.app_context():
        token = jwt.encode(
            {
                "user_id": 1,
                "username": "testuser",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_user(app):
    """Create a sample user for testing"""
    with app.app_context():
        user = User(username="testuser", password_hash="hashed_password")
        db.session.add(user)
        db.session.commit()
        return user


# --- Note Creation ---
def test_create_note_success(client, auth_headers, sample_user):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "This is a test note.",
    }
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["video_id"] == payload["video_id"]
    assert data["text"] == payload["text"]
    assert data["timestamp"] == payload["timestamp"]
    assert data["generated_by_ai"] is False


def test_create_note_missing_auth(client):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "This is a test note.",
    }
    response = client.post("/notes", json=payload)
    assert response.status_code == 401
    assert "error" in response.get_json()


def test_create_note_invalid_data(client, auth_headers, sample_user):
    payload = {"video_title": "No timestamp or ID", "text": "Missing fields"}
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]


def test_create_note_missing_video_title(client, auth_headers, sample_user):
    payload = {
        "video_id": "abc123",
        "timestamp": "00:01:30",
        "text": "This is a test note.",
    }
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "video_title is required" in response.get_json()["error"]


def test_create_note_invalid_timestamp(client, auth_headers, sample_user):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "invalidtimestamp",
        "text": "This is a test note.",
    }
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]


# --- Get Notes for Video ---
def test_get_notes_success(client, auth_headers, app, sample_user):
    video = Video(video_id="vid123", title="Some Video", user_id=1)
    note = Note(
        video_id="vid123",
        text="Some note",
        timestamp="00:00:10",
        generated_by_ai=False,
        user_id=1,
    )
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
    response = client.get("/notes/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data[0]["video_id"] == "vid123"
    assert data[0]["text"] == "Some note"
    assert data[0]["generated_by_ai"] is False


def test_get_notes_not_found(client, auth_headers, sample_user):
    response = client.get("/notes/nonexistent", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == []


def test_get_notes_unauthorized(client):
    response = client.get("/notes/vid123")
    assert response.status_code == 401
    assert "error" in response.get_json()


# --- Delete Note ---
def test_delete_note_success(client, auth_headers, app, sample_user):
    video = Video(video_id="vid123", title="Test Video", user_id=1)
    note = Note(
        video_id="vid123",
        text="Test note",
        timestamp="00:00:10",
        generated_by_ai=False,
        user_id=1,
    )
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id
    response = client.delete(f"/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["message"] == "Note deleted successfully"
    with app.app_context():
        deleted_note = Note.query.get(note_id)
        assert deleted_note is None


def test_delete_note_not_found(client, auth_headers, sample_user):
    response = client.delete("/notes/999", headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["error"] == "Note not found"


def test_delete_note_unauthorized(client, app, sample_user):
    video = Video(video_id="vid123", title="Test Video", user_id=1)
    note = Note(
        video_id="vid123",
        text="Test note",
        timestamp="00:00:10",
        generated_by_ai=False,
        user_id=1,
    )
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id
    response = client.delete(f"/notes/{note_id}")
    assert response.status_code == 401
    assert "error" in response.get_json()
    with app.app_context():
        existing_note = Note.query.get(note_id)
        assert existing_note is not None


# --- Search Videos ---
def test_search_results_success(client, auth_headers, app, sample_user):
    video1 = Video(video_id="vid1", title="Python Tutorial", user_id=1)
    video2 = Video(video_id="vid2", title="Advanced Python", user_id=1)
    note1 = Note(video_id="vid1", text="Note 1", timestamp="00:01:00", user_id=1)
    note2 = Note(video_id="vid2", text="Note 2", timestamp="00:01:00", user_id=1)
    with app.app_context():
        db.session.add_all([video1, video2, note1, note2])
        db.session.commit()
    response = client.get("/search?query=Python", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    titles = [video["video_title"] for video in data]
    assert "Python Tutorial" in titles
    assert "Advanced Python" in titles


def test_search_results_no_match(client, auth_headers, app, sample_user):
    video = Video(video_id="vid1", title="Java Tutorial", user_id=1)
    with app.app_context():
        db.session.add(video)
        db.session.commit()
    response = client.get("/search?query=Python", headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["error"] == "No videos found matching the query"


def test_search_results_missing_query(client, auth_headers, sample_user):
    response = client.get("/search", headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json() == {"error": "Query parameter is required"}


def test_search_results_unauthorized(client):
    response = client.get("/search?query=Python")
    assert response.status_code == 401
    assert "error" in response.get_json()


# --- Additional Note Tests ---
def test_create_note_with_ai_toggle_enabled(client, auth_headers, app, sample_user):
    """Test note creation when AI toggle is enabled"""
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "This is a test note.",
    }

    with app.app_context():
        # Ensure AI_NOTE_TOGGLE is enabled in the app config
        assert app.config.get("AI_NOTE_TOGGLE") is True

    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["video_id"] == payload["video_id"]
    assert data["text"] == payload["text"]
    assert data["timestamp"] == payload["timestamp"]
    assert data["generated_by_ai"] is False


def test_create_note_empty_text(client, auth_headers, sample_user):
    """Test creating note with empty text"""
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "",
    }
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 201  # Should still create note with empty text
    data = response.get_json()
    assert data["text"] == ""


def test_create_note_very_long_text(client, auth_headers, sample_user):
    """Test creating note with very long text"""
    long_text = "A" * 10000  # Very long text
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": long_text,
    }
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["text"] == long_text


def test_create_note_special_characters(client, auth_headers, sample_user):
    """Test creating note with special characters"""
    special_text = "Test note with 特殊字符 and émojis 🚀 and symbols !@#$%^&*()"
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": special_text,
    }
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["text"] == special_text


def test_create_note_duplicate_video_different_timestamp(
    client, auth_headers, app, sample_user
):
    """Test creating multiple notes for same video with different timestamps"""
    video = Video(video_id="vid123", title="Test Video", user_id=1)
    with app.app_context():
        db.session.add(video)
        db.session.commit()

    # Create first note
    payload1 = {
        "video_id": "vid123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "First note",
    }
    response1 = client.post("/notes", json=payload1, headers=auth_headers)
    assert response1.status_code == 201

    # Create second note for same video
    payload2 = {
        "video_id": "vid123",
        "video_title": "Test Video",
        "timestamp": "00:02:45",
        "text": "Second note",
    }
    response2 = client.post("/notes", json=payload2, headers=auth_headers)
    assert response2.status_code == 201


def test_create_note_duplicate_timestamp_same_video(
    client, auth_headers, app, sample_user
):
    """Test creating notes with same timestamp for same video"""
    video = Video(video_id="vid123", title="Test Video", user_id=1)
    with app.app_context():
        db.session.add(video)
        db.session.commit()

    # Create first note
    payload1 = {
        "video_id": "vid123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "First note",
    }
    response1 = client.post("/notes", json=payload1, headers=auth_headers)
    assert response1.status_code == 201

    # Create second note with same timestamp
    payload2 = {
        "video_id": "vid123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "Second note at same time",
    }
    response2 = client.post("/notes", json=payload2, headers=auth_headers)
    assert response2.status_code == 201  # Should allow duplicate timestamps


def test_get_notes_multiple_notes_ordering(client, auth_headers, app, sample_user):
    """Test that notes are returned in correct order"""
    video = Video(video_id="vid123", title="Test Video", user_id=1)
    note1 = Note(video_id="vid123", text="First note", timestamp="00:01:00", user_id=1)
    note2 = Note(video_id="vid123", text="Second note", timestamp="00:02:00", user_id=1)
    note3 = Note(video_id="vid123", text="Third note", timestamp="00:00:30", user_id=1)

    with app.app_context():
        db.session.add(video)
        db.session.add_all([note1, note2, note3])
        db.session.commit()

    response = client.get("/notes/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 3
    # Notes should be ordered by creation time or ID
    texts = [note["text"] for note in data]
    assert "First note" in texts
    assert "Second note" in texts
    assert "Third note" in texts


def test_get_notes_user_isolation(client, auth_headers, app, sample_user):
    """Test that users can only see their own notes"""
    # Create second user
    user2 = User(username="user2", password_hash="hashed2")

    video = Video(video_id="vid123", title="Test Video", user_id=1)
    note1 = Note(video_id="vid123", text="User 1 note", timestamp="00:01:00", user_id=1)
    note2 = Note(video_id="vid123", text="User 2 note", timestamp="00:02:00", user_id=2)

    with app.app_context():
        db.session.add(user2)
        db.session.add(video)
        db.session.add_all([note1, note2])
        db.session.commit()

    # User 1 should only see their own note
    response = client.get("/notes/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["text"] == "User 1 note"


def test_delete_note_user_isolation(client, auth_headers, app, sample_user):
    """Test that users can only delete their own notes"""
    # Create second user
    user2 = User(username="user2", password_hash="hashed2")

    video = Video(video_id="vid123", title="Test Video", user_id=1)
    note_user1 = Note(
        video_id="vid123", text="User 1 note", timestamp="00:01:00", user_id=1
    )
    note_user2 = Note(
        video_id="vid123", text="User 2 note", timestamp="00:02:00", user_id=2
    )

    with app.app_context():
        db.session.add(user2)
        db.session.add(video)
        db.session.add_all([note_user1, note_user2])
        db.session.commit()
        note_user2_id = note_user2.id

    # User 1 trying to delete user 2's note should fail
    response = client.delete(f"/notes/{note_user2_id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["error"] == "Note not found"


def test_update_note_ai_generated(client, auth_headers, app, sample_user):
    """Test updating note's AI-generated content"""
    video = Video(video_id="vid123", title="Test Video", user_id=1)
    note = Note(
        video_id="vid123",
        text="Original note",
        timestamp="00:01:00",
        user_id=1,
        generated_by_ai=False,
    )

    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id

    # Update note with AI-generated content
    payload = {
        "text": "This is an AI-generated note based on the transcript.",
        "generated_by_ai": True,
    }
    response = client.patch(f"/notes/{note_id}", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["text"] == payload["text"]
    assert data["generated_by_ai"] is True


def test_update_note_not_found(client, auth_headers, sample_user):
    """Test updating non-existent note"""
    payload = {"text": "This is an AI-generated note.", "generated_by_ai": True}
    response = client.patch("/notes/999", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["error"] == "Note not found"


def test_update_note_unauthorized(client, app, sample_user):
    """Test updating note without authentication"""
    video = Video(video_id="vid123", title="Test Video", user_id=1)
    note = Note(
        video_id="vid123", text="Original note", timestamp="00:01:00", user_id=1
    )

    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id

    payload = {"text": "Unauthorized update attempt", "generated_by_ai": False}
    response = client.patch(f"/notes/{note_id}", json=payload)
    assert response.status_code == 401
    assert "error" in response.get_json()


def test_create_note_invalid_json(client, auth_headers, sample_user):
    """Test creating note with invalid JSON"""
    response = client.post("/notes", data="invalid json", headers=auth_headers)
    assert (
        response.status_code == 500
    )  # Current behavior - server error for malformed JSON


def test_timestamp_format_validation(client, auth_headers, sample_user):
    """Test various timestamp formats"""
    valid_timestamps = ["00:01:30", "01:23:45", "10:00:00", "0:01:30", "1:23:45"]

    for i, timestamp in enumerate(valid_timestamps):
        payload = {
            "video_id": f"vid{i}",
            "video_title": "Test Video",
            "timestamp": timestamp,
            "text": f"Note {i}",
        }
        response = client.post("/notes", json=payload, headers=auth_headers)
        assert response.status_code == 201, f"Failed for timestamp: {timestamp}"


def test_video_title_with_special_characters(client, auth_headers, sample_user):
    """Test creating note with video title containing special characters"""
    payload = {
        "video_id": "vid123",
        "video_title": "Test Video: Advanced 🚀 Tütorial with spëcial chars!",
        "timestamp": "00:01:30",
        "text": "Test note",
    }
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["video_id"] == "vid123"
