from vidwiz.shared.models import Note, Video, User, db


# --- Note CRUD Operations ---
def test_create_note_success(client, auth_headers, sample_user):
    """Test creating a note"""
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "This is a test note.",
    }
    response = client.post("/api/notes", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["video_id"] == payload["video_id"]
    assert data["text"] == payload["text"]
    assert data["timestamp"] == payload["timestamp"]


def test_create_note_missing_auth(client):
    """Test creating note without authentication"""
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "This is a test note.",
    }
    response = client.post("/api/notes", json=payload)
    assert response.status_code == 401


def test_create_note_invalid_data(client, auth_headers, sample_user):
    """Test creating note with missing required fields"""
    payload = {"text": "Missing video_id and timestamp"}
    response = client.post("/api/notes", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_get_notes_success(client, auth_headers, app, sample_user):
    """Test retrieving notes for a video"""
    with app.app_context():
        video = Video(video_id="vid123", title="Test Video")
        note = Note(
            video_id="vid123",
            text="Test note",
            timestamp="00:01:00",
            user_id=1,
        )
        db.session.add_all([video, note])
        db.session.commit()

    response = client.get("/api/notes/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["text"] == "Test note"


def test_delete_note_success(client, auth_headers, app, sample_user):
    """Test deleting a note"""
    with app.app_context():
        video = Video(video_id="vid123", title="Test Video")
        note = Note(
            video_id="vid123",
            text="Test note",
            timestamp="00:01:00",
            user_id=1,
        )
        db.session.add_all([video, note])
        db.session.commit()
        note_id = note.id

    response = client.delete(f"/api/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 200
    assert "deleted successfully" in response.get_json()["message"]


def test_update_note_success(client, auth_headers, app, sample_user):
    """Test updating a note"""
    with app.app_context():
        video = Video(video_id="vid123", title="Test Video")
        note = Note(
            video_id="vid123",
            text="Original note",
            timestamp="00:01:00",
            user_id=1,
        )
        db.session.add_all([video, note])
        db.session.commit()
        note_id = note.id

    payload = {"text": "Updated note content"}
    response = client.patch(f"/api/notes/{note_id}", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["text"] == payload["text"]


# --- Search Functionality ---
# Note: Main search tests are in test_core_routes.py


# --- Video Operations ---
# Note: Main video tests are in test_video_routes.py


def test_user_isolation(client, auth_headers, app, sample_user):
    """Test that users can only access their own notes"""
    with app.app_context():
        user2 = User(email="user2@example.com", name="User Two", password_hash="hashed2")
        video = Video(video_id="vid123", title="Test Video")
        note1 = Note(
            video_id="vid123", text="User 1 note", timestamp="00:01:00", user_id=1
        )
        note2 = Note(
            video_id="vid123", text="User 2 note", timestamp="00:02:00", user_id=2
        )
        db.session.add_all([user2, video, note1, note2])
        db.session.commit()

    # User 1 should only see their own note
    response = client.get("/api/notes/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["text"] == "User 1 note"
