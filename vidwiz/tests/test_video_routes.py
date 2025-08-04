import pytest
import jwt
from datetime import datetime, timedelta, timezone
from vidwiz.app import create_app
from vidwiz.shared.models import User, Video, Note, db


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": "test_secret_key",
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
    """Create auth headers with valid JWT token"""
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
def auth_headers_user2(app):
    """Create auth headers for second user"""
    with app.app_context():
        token = jwt.encode(
            {
                "user_id": 2,
                "username": "testuser2",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_data(app):
    """Create sample users and videos for testing"""
    with app.app_context():
        # Create users
        user1 = User(username="testuser", password_hash="hashed1")
        user2 = User(username="testuser2", password_hash="hashed2")
        db.session.add_all([user1, user2])
        db.session.commit()

        # Create videos
        video1 = Video(
            video_id="vid123",
            title="Test Video 1",
            transcript_available=True,
            user_id=1,
        )
        video2 = Video(
            video_id="vid456",
            title="Test Video 2",
            transcript_available=False,
            user_id=2,
        )
        video3 = Video(
            video_id="vid789",
            title="Test Video 3",
            transcript_available=True,
            user_id=1,
        )
        db.session.add_all([video1, video2, video3])
        db.session.commit()

        return {"users": [user1, user2], "videos": [video1, video2, video3]}


class TestGetVideoRoute:
    def test_get_video_success(self, client, auth_headers, sample_data):
        """Test successful video retrieval"""
        response = client.get("/videos/vid123", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["video_id"] == "vid123"
        assert data["title"] == "Test Video 1"
        assert data["transcript_available"] is True
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_video_not_found(self, client, auth_headers, sample_data):
        """Test video not found"""
        response = client.get("/videos/nonexistent", headers=auth_headers)
        assert response.status_code == 404

        data = response.get_json()
        assert data["error"] == "Video not found"

    def test_get_video_unauthorized_access(self, client, auth_headers, sample_data):
        """Test accessing video from different user"""
        # Try to access vid456 which belongs to user2 with user1's token
        response = client.get("/videos/vid456", headers=auth_headers)
        assert response.status_code == 404

        data = response.get_json()
        assert data["error"] == "Video not found"

    def test_get_video_no_auth_header(self, client, sample_data):
        """Test video access without authentication"""
        response = client.get("/videos/vid123")
        assert response.status_code == 401

        data = response.get_json()
        assert "error" in data
        assert "Authorization" in data["error"]

    def test_get_video_invalid_token(self, client, sample_data):
        """Test video access with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/videos/vid123", headers=headers)
        assert response.status_code == 401

        data = response.get_json()
        assert data["error"] == "Invalid or expired token"

    def test_get_video_expired_token(self, client, sample_data, app):
        """Test video access with expired token"""
        with app.app_context():
            expired_token = jwt.encode(
                {
                    "user_id": 1,
                    "username": "testuser",
                    "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            headers = {"Authorization": f"Bearer {expired_token}"}

        response = client.get("/videos/vid123", headers=headers)
        assert response.status_code == 401

        data = response.get_json()
        assert data["error"] == "Invalid or expired token"

    def test_get_video_user_isolation(self, client, auth_headers_user2, sample_data):
        """Test that users can only access their own videos"""
        # User2 trying to access their own video (vid456)
        response = client.get("/videos/vid456", headers=auth_headers_user2)
        assert response.status_code == 200

        data = response.get_json()
        assert data["video_id"] == "vid456"
        assert data["title"] == "Test Video 2"

        # User2 trying to access user1's video (vid123)
        response = client.get("/videos/vid123", headers=auth_headers_user2)
        assert response.status_code == 404

        data = response.get_json()
        assert data["error"] == "Video not found"

    def test_get_video_malformed_auth_header(self, client, sample_data):
        """Test video access with malformed authorization header"""
        headers = {"Authorization": "NotBearer token123"}
        response = client.get("/videos/vid123", headers=headers)
        assert response.status_code == 401

        data = response.get_json()
        assert "Authorization" in data["error"]

    def test_get_video_empty_auth_header(self, client, sample_data):
        """Test video access with empty authorization header"""
        headers = {"Authorization": ""}
        response = client.get("/videos/vid123", headers=headers)
        assert response.status_code == 401

        data = response.get_json()
        assert "Authorization" in data["error"]

    def test_get_video_missing_bearer_prefix(self, client, sample_data):
        """Test video access without Bearer prefix in auth header"""
        headers = {"Authorization": "token123"}
        response = client.get("/videos/vid123", headers=headers)
        assert response.status_code == 401

        data = response.get_json()
        assert "Authorization" in data["error"]

    def test_get_video_internal_server_error(self, client, auth_headers, app):
        """Test handling of internal server errors"""
        with app.app_context():
            # Create a scenario that might cause an internal error
            # For this test, we'll simulate by accessing a video with a very long ID
            # that might cause database issues (though this is contrived)
            extremely_long_id = "a" * 10000

        response = client.get(f"/videos/{extremely_long_id}", headers=auth_headers)
        # The specific status code might vary depending on how the database handles this
        # but it should be either 404 (not found) or 500 (internal error)
        assert response.status_code in [404, 500]

    def test_get_video_special_characters_in_id(
        self, client, auth_headers, sample_data
    ):
        """Test video access with special characters in video ID"""
        # Test with URL-encoded special characters
        response = client.get("/videos/vid%20with%20spaces", headers=auth_headers)
        assert response.status_code == 404  # Should not be found

        data = response.get_json()
        assert data["error"] == "Video not found"

    def test_get_video_numeric_id(self, client, auth_headers, app):
        """Test video access with numeric video ID"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(
                video_id="12345",  # Numeric ID as string
                title="Numeric ID Video",
                user_id=1,
            )
            db.session.add(video)
            db.session.commit()

        response = client.get("/videos/12345", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["video_id"] == "12345"
        assert data["title"] == "Numeric ID Video"

    def test_get_video_response_structure(self, client, auth_headers, sample_data):
        """Test that video response has correct structure"""
        response = client.get("/videos/vid123", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()

        # Check required fields
        required_fields = [
            "video_id",
            "title",
            "transcript_available",
            "created_at",
            "updated_at",
            "user_id",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check data types
        assert isinstance(data["video_id"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["transcript_available"], bool)
        assert isinstance(data["user_id"], int)
        assert isinstance(data["created_at"], str)  # Should be ISO format string
        assert isinstance(data["updated_at"], str)  # Should be ISO format string

    def test_get_video_with_notes_relationship(self, client, auth_headers, app):
        """Test video retrieval when video has associated notes"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(
                video_id="vid_with_notes", title="Video with Notes", user_id=1
            )
            db.session.add(video)
            db.session.commit()

            # Add some notes to the video
            note1 = Note(
                video_id="vid_with_notes",
                timestamp="00:01:30",
                text="First note",
                user_id=1,
            )
            note2 = Note(
                video_id="vid_with_notes",
                timestamp="00:02:45",
                text="Second note",
                user_id=1,
            )
            db.session.add_all([note1, note2])
            db.session.commit()

        response = client.get("/videos/vid_with_notes", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["video_id"] == "vid_with_notes"
        assert data["title"] == "Video with Notes"
        # Note: The current implementation doesn't include notes in the response
        # This test ensures the video can still be retrieved when it has notes

    def test_get_video_very_long_video_id(self, client, auth_headers, sample_data):
        """Test get video with very long video ID"""
        with client.application.app_context():
            long_video_id = "a" * 500  # Very long video ID
            video = Video(
                video_id=long_video_id,
                title="Long ID Video",
                user_id=1,
            )
            db.session.add(video)
            db.session.commit()

        response = client.get(f"/videos/{long_video_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["video_id"] == long_video_id

    def test_get_video_unicode_characters(self, client, auth_headers, sample_data):
        """Test get video with unicode characters in video ID"""
        with client.application.app_context():
            unicode_video_id = "vid_测试_🎥"
            video = Video(
                video_id=unicode_video_id,
                title="Unicode Video",
                user_id=1,
            )
            db.session.add(video)
            db.session.commit()

        # URL encode the unicode characters
        import urllib.parse

        encoded_id = urllib.parse.quote(unicode_video_id, safe="")

        response = client.get(f"/videos/{encoded_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["video_id"] == unicode_video_id

    def test_get_video_boolean_transcript_flag(self, client, auth_headers, sample_data):
        """Test that transcript_available boolean is correctly returned"""
        with client.application.app_context():
            # Test with transcript available
            video_with_transcript = Video(
                video_id="vid_with_transcript",
                title="Video with Transcript",
                transcript_available=True,
                user_id=1,
            )
            # Test with transcript not available
            video_without_transcript = Video(
                video_id="vid_without_transcript",
                title="Video without Transcript",
                transcript_available=False,
                user_id=1,
            )
            db.session.add_all([video_with_transcript, video_without_transcript])
            db.session.commit()

        # Test video with transcript
        response = client.get("/videos/vid_with_transcript", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["transcript_available"] is True

        # Test video without transcript
        response = client.get("/videos/vid_without_transcript", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["transcript_available"] is False
