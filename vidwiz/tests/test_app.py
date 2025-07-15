import pytest
from vidwiz.app import create_app
from vidwiz.shared.models import Note, Video, db

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

# --- Note Creation ---
def test_create_note_success(client):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "This is a test note."
    }
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
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
        "text": "This is a test note."
    }
    response = client.post("/notes", json=payload)
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_create_note_invalid_data(client):
    payload = {"video_title": "No timestamp or ID", "text": "Missing fields"}
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]


def test_create_note_missing_video_title(client):
    payload = {
        "video_id": "abc123",
        "timestamp": "00:01:30",
        "text": "This is a test note."
    }
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "video_title is required" in response.get_json()["error"]


def test_create_note_invalid_timestamp(client):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "invalidtimestamp",
        "text": "This is a test note."
    }
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]

# --- Get Notes for Video ---
def test_get_notes_success(client, app):
    video = Video(video_id="vid123", title="Some Video")
    note = Note(video_id="vid123", text="Some note", timestamp="00:00:10", generated_by_ai=False)
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
    response = client.get("/notes/vid123", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data[0]["video_id"] == "vid123"
    assert data[0]["text"] == "Some note"
    assert data[0]["generated_by_ai"] is False


def test_get_notes_not_found(client):
    response = client.get("/notes/nonexistent", headers=AUTH_HEADER)
    assert response.status_code == 200
    assert response.get_json() == []


def test_get_notes_unauthorized(client):
    response = client.get("/notes/vid123")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"

# --- Delete Note ---
def test_delete_note_success(client, app):
    video = Video(video_id="vid123", title="Test Video")
    note = Note(video_id="vid123", text="Test note", timestamp="00:00:10", generated_by_ai=False)
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id
    response = client.delete(f"/note/{note_id}", headers=AUTH_HEADER)
    assert response.status_code == 200
    assert response.get_json()["message"] == "Note deleted successfully"
    with app.app_context():
        deleted_note = Note.query.get(note_id)
        assert deleted_note is None


def test_delete_note_not_found(client):
    response = client.delete("/note/999", headers=AUTH_HEADER)
    assert response.status_code == 404
    assert response.get_json()["error"] == "Note not found"


def test_delete_note_unauthorized(client, app):
    video = Video(video_id="vid123", title="Test Video")
    note = Note(video_id="vid123", text="Test note", timestamp="00:00:10", generated_by_ai=False)
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id
    response = client.delete(f"/note/{note_id}")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"
    with app.app_context():
        existing_note = Note.query.get(note_id)
        assert existing_note is not None

# --- Search Videos ---
def test_search_results_success(client, app):
    video1 = Video(video_id="vid1", title="Python Tutorial")
    video2 = Video(video_id="vid2", title="Advanced Python")
    with app.app_context():
        db.session.add_all([video1, video2])
        db.session.commit()
    response = client.get("/search?query=Python", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    titles = [video["video_title"] for video in data]
    assert "Python Tutorial" in titles
    assert "Advanced Python" in titles


def test_search_results_no_match(client, app):
    video = Video(video_id="vid1", title="Java Tutorial")
    with app.app_context():
        db.session.add(video)
        db.session.commit()
    response = client.get("/search?query=Python", headers=AUTH_HEADER)
    assert response.status_code == 404
    assert response.get_json()["error"] == "No videos found matching the query"


def test_search_results_missing_query(client):
    response = client.get("/search", headers=AUTH_HEADER)
    assert response.status_code == 400
    assert response.get_json() == {"error": "Query parameter is required"}


def test_search_results_unauthorized(client):
    response = client.get("/search?query=Python")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"
