import pytest
from vidwiz.shared.models import User, Video, db

# Test constants
VIDEO_IDS = ["vid123", "vid456", "vid789"]
VIDEO_TITLES = ["Test Video 1", "Test Video 2", "Test Video 3"]
TRANSCRIPT_AVAILABILITY = [True, False, True]


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
        videos = []
        for i, (video_id, title, transcript) in enumerate(
            zip(VIDEO_IDS, VIDEO_TITLES, TRANSCRIPT_AVAILABILITY)
        ):
            video = Video(
                video_id=video_id,
                title=title,
                transcript_available=transcript,
            )
            videos.append(video)

        db.session.add_all(videos)
        db.session.commit()

        return {"users": [user1, user2], "videos": videos}


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
        """Test accessing video with valid authentication - videos are public"""
        # All videos are accessible to any authenticated user
        response = client.get("/videos/vid456", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["video_id"] == "vid456"
        assert data["title"] == "Test Video 2"

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
        assert data["error"] == "Invalid or expired token or not a long term token"

    def test_get_video_response_structure(self, client, auth_headers, sample_data):
        """Test that video response has correct structure"""
        response = client.get("/videos/vid123", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()

        # Check required fields
        required_fields = [
            "id",
            "video_id",
            "title",
            "transcript_available",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check data types
        assert isinstance(data["id"], int)
        assert isinstance(data["video_id"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["transcript_available"], bool)
