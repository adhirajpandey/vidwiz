import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from vidwiz.app import create_app
from vidwiz.shared.models import User, Note, db
from werkzeug.security import generate_password_hash


@pytest.fixture
def notes_app():
    """App fixture with specific notes test configuration"""
    app = create_app(
        {
            "TESTING": True,
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
def notes_client(notes_app):
    """Client for notes testing with specific config"""
    return notes_app.test_client()


@pytest.fixture
def notes_auth_headers(notes_app):
    """Create auth headers with valid JWT token for notes tests"""
    with notes_app.app_context():
        token = jwt.encode(
            {
                "user_id": 1,
                "username": "testuser",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            notes_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def notes_sample_user(notes_app):
    """Create a sample user for notes testing"""
    with notes_app.app_context():
        user = User(
            username="testuser", password_hash=generate_password_hash("testpass123")
        )
        db.session.add(user)
        db.session.commit()
        return user


class TestCreateNote:
    """Test note creation endpoint"""

    def test_create_note_success_with_existing_video(
        self, client, auth_headers, app, sample_user, sample_video
    ):
        """Test creating a note with existing video"""
        with app.app_context():
            response = client.post(
                "/notes",
                headers=auth_headers,
                json={
                    "video_id": "test_video_123",
                    "text": "This is a test note",
                    "timestamp": "1:23",
                },
            )

            assert response.status_code == 201
            data = response.get_json()
            assert data["video_id"] == "test_video_123"
            assert data["text"] == "This is a test note"
            assert data["timestamp"] == "1:23"
            assert data["generated_by_ai"] is False
            assert data["user_id"] == 1

    def test_create_note_with_new_video(self, client, auth_headers, app, sample_user):
        """Test creating a note with a new video that doesn't exist"""
        with patch("vidwiz.routes.notes_routes.create_transcript_task") as mock_task:
            response = client.post(
                "/notes",
                headers=auth_headers,
                json={
                    "video_id": "new_video_456",
                    "video_title": "New Video Title",
                    "text": "Note for new video",
                    "timestamp": "2:45",
                },
            )

            assert response.status_code == 201
            data = response.get_json()
            assert data["video_id"] == "new_video_456"
            assert data["text"] == "Note for new video"
            mock_task.assert_called_once_with("new_video_456")

    def test_create_note_missing_video_title(
        self, client, auth_headers, app, sample_user
    ):
        """Test creating a note for non-existent video without video_title"""
        response = client.post(
            "/notes",
            headers=auth_headers,
            json={
                "video_id": "nonexistent_video",
                "text": "This should fail",
                "timestamp": "1:00",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "video_title is required" in data["error"]

    @patch("vidwiz.routes.notes_routes.send_request_to_ainote_lambda")
    def test_create_note_triggers_ai_generation(
        self,
        mock_lambda,
        notes_client,
        notes_auth_headers,
        notes_app,
        notes_sample_user,
    ):
        """Test that AI note generation is triggered when appropriate"""
        from vidwiz.shared.models import Video

        with notes_app.app_context():
            # Create video with transcript available
            video = Video(
                video_id="test_video_123",
                title="Test Video Title",
                transcript_available=True,
            )
            db.session.add(video)
            db.session.commit()

            response = notes_client.post(
                "/notes",
                headers=notes_auth_headers,
                json={
                    "video_id": "test_video_123",
                    "timestamp": "3:30",
                    # No text provided - should trigger AI
                },
            )

            assert response.status_code == 201
            mock_lambda.assert_called_once()

    def test_create_note_no_auth(self, client):
        """Test creating note without authentication"""
        response = client.post(
            "/notes",
            json={
                "video_id": "test_video",
                "text": "Unauthorized note",
                "timestamp": "1:00",
            },
        )

        assert response.status_code == 401

    def test_create_note_invalid_data(self, client, auth_headers):
        """Test creating note with invalid data"""
        response = client.post(
            "/notes",
            headers=auth_headers,
            json={
                "video_id": "",  # Invalid empty video_id
                "text": "Test note",
                "timestamp": "invalid_timestamp",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid data" in data["error"]

    def test_create_note_no_json_body(self, client, auth_headers):
        """Test creating note without JSON body"""
        # When json=None is passed, request.json becomes None,
        # and NoteCreate(**None) causes TypeError -> 500 error
        response = client.post("/notes", headers=auth_headers, json=None)

        assert response.status_code == 500
        data = response.get_json()
        assert "Internal Server Error" in data["error"]


class TestGetNotes:
    """Test getting notes for a video"""

    def test_get_notes_success(
        self, client, auth_headers, app, sample_user, sample_video
    ):
        """Test getting notes for a video"""
        with app.app_context():
            # Create some notes
            note1 = Note(
                video_id="test_video_123",
                text="First note",
                timestamp="1:00",
                user_id=1,
            )
            note2 = Note(
                video_id="test_video_123",
                text="Second note",
                timestamp="2:00",
                user_id=1,
            )
            db.session.add_all([note1, note2])
            db.session.commit()

            response = client.get("/notes/test_video_123", headers=auth_headers)

            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 2
            assert {note["text"] for note in data} == {"First note", "Second note"}

    def test_get_notes_empty_list(self, client, auth_headers, app, sample_user):
        """Test getting notes for video with no notes"""
        response = client.get("/notes/no_notes_video", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_get_notes_no_auth(self, client):
        """Test getting notes without authentication"""
        response = client.get("/notes/test_video")

        assert response.status_code == 401

    def test_get_notes_only_user_notes(self, client, app, sample_video):
        """Test that users only see their own notes"""
        with app.app_context():
            # Create users
            user1 = User(
                username="user1", password_hash=generate_password_hash("pass1")
            )
            user2 = User(
                username="user2", password_hash=generate_password_hash("pass2")
            )
            db.session.add_all([user1, user2])
            db.session.commit()

            # Create notes for both users
            note1 = Note(
                video_id="test_video_123",
                text="User 1 note",
                timestamp="1:00",
                user_id=user1.id,
            )
            note2 = Note(
                video_id="test_video_123",
                text="User 2 note",
                timestamp="2:00",
                user_id=user2.id,
            )
            db.session.add_all([note1, note2])
            db.session.commit()

            # Create token for user1
            token = jwt.encode(
                {
                    "user_id": user1.id,
                    "username": "user1",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            headers = {"Authorization": f"Bearer {token}"}

            response = client.get("/notes/test_video_123", headers=headers)

            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 1
            assert data[0]["text"] == "User 1 note"
            assert data[0]["user_id"] == user1.id


class TestDeleteNote:
    """Test note deletion endpoint"""

    def test_delete_note_success(
        self, client, auth_headers, app, sample_user, sample_video
    ):
        """Test deleting a note successfully"""
        with app.app_context():
            note = Note(
                video_id="test_video_123",
                text="Note to delete",
                timestamp="1:00",
                user_id=1,
            )
            db.session.add(note)
            db.session.commit()
            note_id = note.id

            response = client.delete(f"/notes/{note_id}", headers=auth_headers)

            assert response.status_code == 200
            data = response.get_json()
            assert "Note deleted successfully" in data["message"]

            # Verify note was deleted
            deleted_note = db.session.get(Note, note_id)
            assert deleted_note is None

    def test_delete_note_not_found(self, client, auth_headers):
        """Test deleting non-existent note"""
        response = client.delete("/notes/999", headers=auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert "Note not found" in data["error"]

    def test_delete_note_wrong_user(self, client, app, sample_video):
        """Test that users can only delete their own notes"""
        with app.app_context():
            # Create two users
            user1 = User(
                username="user1", password_hash=generate_password_hash("pass1")
            )
            user2 = User(
                username="user2", password_hash=generate_password_hash("pass2")
            )
            db.session.add_all([user1, user2])
            db.session.commit()

            # Create note for user1
            note = Note(
                video_id="test_video_123",
                text="User 1 note",
                timestamp="1:00",
                user_id=user1.id,
            )
            db.session.add(note)
            db.session.commit()
            note_id = note.id

            # Try to delete with user2's token
            token = jwt.encode(
                {
                    "user_id": user2.id,
                    "username": "user2",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            headers = {"Authorization": f"Bearer {token}"}

            response = client.delete(f"/notes/{note_id}", headers=headers)

            assert response.status_code == 404  # Note not found (for this user)

            # Verify note still exists
            existing_note = db.session.get(Note, note_id)
            assert existing_note is not None

    def test_delete_note_no_auth(self, client):
        """Test deleting note without authentication"""
        response = client.delete("/notes/1")

        assert response.status_code == 401
