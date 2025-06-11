import pytest
from app import create_app
from models import Note, db

# Define a test token to use in tests
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


def test_create_note_success(client):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "note_timestamp": "00:01:30",
        "note": "This is a test note.",
    }
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 201
    data = response.get_json()
    assert data["video_id"] == payload["video_id"]
    assert data["note"] == payload["note"]
    assert data["ai_note"] is None


def test_create_note_unauthorized(client):
    payload = {
        "video_id": "abc123",
        "note_timestamp": "00:01:30",
        "note": "This is a test note.",
    }
    response = client.post("/notes", json=payload)
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_create_note_invalid_data(client):
    payload = {"video_title": "No timestamp or ID", "note": "Missing fields"}
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]


def test_create_note_empty_video_title(client):
    payload = {
        "video_id": "abc123",
        "video_title": "",
        "note_timestamp": "00:01:30",
        "note": "This is a test note.",
    }
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "video_title cannot be empty" in response.get_json()["error"]


def test_create_note_invalid_timestamp_data(client):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "note_timestamp": "{lv=screenContent[com.google.android.youtube:id/time_bar_current_time]}",
        "note": "This is a test note.",
    }
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]


def test_get_notes_by_video_success(client, app):
    note = Note(
        video_id="vid123",
        video_title="Some Video",
        note_timestamp="00:00:10",
        note="Some note",
        ai_note=None
    )
    with app.app_context():
        db.session.add(note)
        db.session.commit()

    response = client.get("/notes/vid123", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data[0]["video_id"] == "vid123"
    assert data[0]["note"] == "Some note"
    assert data[0]["ai_note"] is None


def test_get_notes_by_video_with_ai_note(client, app):
    note = Note(
        video_id="vid123",
        video_title="Some Video",
        note_timestamp="00:00:10",
        note=None,
        ai_note="AI generated note"
    )
    with app.app_context():
        db.session.add(note)
        db.session.commit()

    response = client.get("/notes/vid123", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data[0]["video_id"] == "vid123"
    assert data[0]["note"] is None
    assert data[0]["ai_note"] == "AI generated note"


def test_get_notes_by_video_not_found(client):
    response = client.get("/notes/nonexistent", headers=AUTH_HEADER)
    assert response.status_code == 404


def test_search_results_success(client, app):
    notes = [
        Note(
            video_id="vid1",
            video_title="Python Tutorial",
            note_timestamp="00:01:00",
            note="Introduction to Python",
            ai_note=None
        ),
        Note(
            video_id="vid2",
            video_title="Advanced Python",
            note_timestamp="00:02:00",
            note="Decorators in Python",
            ai_note=None
        ),
    ]
    with app.app_context():
        db.session.bulk_save_objects(notes)
        db.session.commit()

    response = client.get("/search?query=Python", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    titles = [video["video_title"] for video in data]
    assert "Python Tutorial" in titles
    assert "Advanced Python" in titles


def test_search_results_no_match(client, app):
    note = Note(
        video_id="vid1",
        video_title="Java Tutorial",
        note_timestamp="00:01:00",
        note="Introduction to Java",
    )
    with app.app_context():
        db.session.add(note)
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
