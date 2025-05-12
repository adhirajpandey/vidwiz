import pytest
from app import create_app, db, Note

# Define a test token to use in tests
AUTH_TOKEN = "testtoken123"
AUTH_HEADER = {"Authorization": f"Bearer {AUTH_TOKEN}"}


@pytest.fixture
def client():
    # Create the app with test configuration
    app = create_app(
        {
            "TESTING": True,
            "AUTH_TOKEN": AUTH_TOKEN,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )

    # Set up and tear down the test database
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()


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


def test_create_note_unauthorized(client):
    payload = {
        "video_id": "abc123",
        "note_timestamp": "00:01:30",
        "note": "This is a test note.",
    }
    response = client.post("/notes", json=payload)  # Missing Authorization header
    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_create_note_invalid_data(client):
    payload = {"video_title": "No timestamp or ID", "note": "Missing fields"}
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]


def test_create_note_invalid_timestamp_data(client):
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        # as sometimes, macrodroid may not be able to get the correct timestamp
        "note_timestamp": "{lv=screenContent[com.google.android.youtube:id/time_bar_current_time]}",
        "note": "This is a test note.",
    }
    response = client.post("/notes", json=payload, headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "Invalid data" in response.get_json()["error"]


def test_get_notes_by_video_success(client):
    note = Note(
        video_id="vid123",
        video_title="Some Video",
        note_timestamp="00:00:10",
        note="Some note",
    )
    with client.application.app_context():
        db.session.add(note)
        db.session.commit()

    response = client.get("/notes/vid123", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data[0]["video_id"] == "vid123"
    assert data[0]["note"] == "Some note"


def test_get_notes_by_video_not_found(client):
    response = client.get("/notes/nonexistent", headers=AUTH_HEADER)
    assert response.status_code == 404


def test_search_results_success(client):
    notes = [
        Note(
            video_id="vid1",
            video_title="Python Tutorial",
            note_timestamp="00:01:00",
            note="Introduction to Python",
        ),
        Note(
            video_id="vid2",
            video_title="Advanced Python",
            note_timestamp="00:02:00",
            note="Decorators in Python",
        ),
    ]
    with client.application.app_context():
        db.session.bulk_save_objects(notes)
        db.session.commit()

    # Perform a search query
    response = client.get("/search?query=Python", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["video_title"] == "Python Tutorial"
    assert data[1]["video_title"] == "Advanced Python"


def test_search_results_no_match(client):
    note = Note(
        video_id="vid1",
        video_title="Java Tutorial",
        note_timestamp="00:01:00",
        note="Introduction to Java",
    )
    with client.application.app_context():
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
