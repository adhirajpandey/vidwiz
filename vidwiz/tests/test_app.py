import pytest
from vidwiz.app import create_app
from vidwiz.shared.models import Note, Video, User, db
import jwt
from datetime import datetime, timedelta, timezone


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": "test_secret_key",
            "AI_NOTE_TOGGLE": False,  # Disable AI to simplify tests
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


# --- Authentication Tests ---
def test_signup_success(client):
    """Test user registration"""
    payload = {"username": "newuser", "password": "password123"}
    response = client.post("/signup", json=payload)
    assert response.status_code == 201
    assert "User created successfully" in response.get_json()["message"]


def test_login_success(client, app):
    """Test user login"""
    # Create user first
    with app.app_context():
        from werkzeug.security import generate_password_hash

        user = User(
            username="testuser", password_hash=generate_password_hash("password")
        )
        db.session.add(user)
        db.session.commit()

    payload = {"username": "testuser", "password": "password"}
    response = client.post("/login", json=payload)
    assert response.status_code == 200
    assert "token" in response.get_json()


def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    payload = {"username": "invalid", "password": "wrong"}
    response = client.post("/login", json=payload)
    assert response.status_code == 401
    assert "Invalid username or password" in response.get_json()["error"]


# --- Note CRUD Operations ---
def test_create_note_success(client, auth_headers, sample_user):
    """Test creating a note"""
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


def test_create_note_missing_auth(client):
    """Test creating note without authentication"""
    payload = {
        "video_id": "abc123",
        "video_title": "Test Video",
        "timestamp": "00:01:30",
        "text": "This is a test note.",
    }
    response = client.post("/notes", json=payload)
    assert response.status_code == 401


def test_create_note_invalid_data(client, auth_headers, sample_user):
    """Test creating note with missing required fields"""
    payload = {"text": "Missing video_id and timestamp"}
    response = client.post("/notes", json=payload, headers=auth_headers)
    assert response.status_code == 400


def test_get_notes_success(client, auth_headers, app, sample_user):
    """Test retrieving notes for a video"""
    video = Video(video_id="vid123", title="Test Video")
    note = Note(
        video_id="vid123",
        text="Test note",
        timestamp="00:01:00",
        user_id=1,
    )
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()

    response = client.get("/notes/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["text"] == "Test note"


def test_delete_note_success(client, auth_headers, app, sample_user):
    """Test deleting a note"""
    video = Video(video_id="vid123", title="Test Video")
    note = Note(
        video_id="vid123",
        text="Test note",
        timestamp="00:01:00",
        user_id=1,
    )
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id

    response = client.delete(f"/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 200
    assert "deleted successfully" in response.get_json()["message"]


def test_update_note_success(client, auth_headers, app, sample_user):
    """Test updating a note"""
    video = Video(video_id="vid123", title="Test Video")
    note = Note(
        video_id="vid123",
        text="Original note",
        timestamp="00:01:00",
        user_id=1,
    )
    with app.app_context():
        db.session.add(video)
        db.session.add(note)
        db.session.commit()
        note_id = note.id

    payload = {"text": "Updated note content"}
    response = client.patch(f"/notes/{note_id}", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["text"] == payload["text"]


# --- Search Functionality ---
def test_search_success(client, auth_headers, app, sample_user):
    """Test search functionality"""
    video = Video(video_id="vid1", title="Python Tutorial")
    note = Note(video_id="vid1", text="Note", timestamp="00:01:00", user_id=1)
    with app.app_context():
        db.session.add_all([video, note])
        db.session.commit()

    response = client.get("/search?query=Python", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["video_title"] == "Python Tutorial"


def test_search_no_results(client, auth_headers, sample_user):
    """Test search with no results"""
    response = client.get("/search?query=NonExistent", headers=auth_headers)
    assert response.status_code == 404


def test_search_missing_query(client, auth_headers, sample_user):
    """Test search without query parameter"""
    response = client.get("/search", headers=auth_headers)
    assert response.status_code == 400


# --- Video Operations ---
def test_get_video_success(client, auth_headers, app):
    """Test retrieving video details"""
    video = Video(video_id="vid123", title="Test Video")
    with app.app_context():
        db.session.add(video)
        db.session.commit()

    response = client.get("/videos/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["video_id"] == "vid123"
    assert data["title"] == "Test Video"


def test_get_video_not_found(client, auth_headers):
    """Test retrieving non-existent video"""
    response = client.get("/videos/nonexistent", headers=auth_headers)
    assert response.status_code == 404


# --- User Isolation ---
def test_user_isolation(client, auth_headers, app, sample_user):
    """Test that users can only access their own notes"""
    user2 = User(username="user2", password_hash="hashed2")
    video = Video(video_id="vid123", title="Test Video")
    note1 = Note(video_id="vid123", text="User 1 note", timestamp="00:01:00", user_id=1)
    note2 = Note(video_id="vid123", text="User 2 note", timestamp="00:02:00", user_id=2)

    with app.app_context():
        db.session.add_all([user2, video, note1, note2])
        db.session.commit()

    # User 1 should only see their own note
    response = client.get("/notes/vid123", headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["text"] == "User 1 note"
