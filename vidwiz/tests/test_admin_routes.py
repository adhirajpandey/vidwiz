import os
from unittest.mock import patch
from vidwiz.shared.models import User, Video, Note, db
from werkzeug.security import generate_password_hash

# Test constants
ADMIN_TOKEN_ENV_VAR = "admin_test_token"
TEST_VIDEO_ID = "new_video_123"
TEST_VIDEO_TITLE = "New Test Video"
EXISTING_VIDEO_ID = "duplicate_video"


class TestAdminRoutes:
    """Test admin routes with proper authentication"""

    @patch.dict(os.environ, {"ADMIN_TOKEN": ADMIN_TOKEN_ENV_VAR})
    @patch("vidwiz.routes.admin_routes.create_transcript_task")
    def test_create_video_success(self, mock_task, client, admin_headers):
        """Test creating a video successfully"""
        response = client.post(
            "/admin/videos",
            headers=admin_headers,
            json={
                "video_id": TEST_VIDEO_ID,
                "title": TEST_VIDEO_TITLE,
                "transcript_available": True,
            },
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["video_id"] == TEST_VIDEO_ID
        assert data["title"] == TEST_VIDEO_TITLE
        assert data["transcript_available"] is True
        mock_task.assert_called_once_with(TEST_VIDEO_ID)

    @patch.dict(os.environ, {"ADMIN_TOKEN": ADMIN_TOKEN_ENV_VAR})
    def test_create_video_duplicate_id(self, client, admin_headers, app):
        """Test creating video with duplicate ID"""
        with app.app_context():
            existing_video = Video(video_id=EXISTING_VIDEO_ID, title="Existing Video")
            db.session.add(existing_video)
            db.session.commit()

        response = client.post(
            "/admin/videos",
            headers=admin_headers,
            json={"video_id": EXISTING_VIDEO_ID, "title": "New Video with Same ID"},
        )

        assert response.status_code == 409
        data = response.get_json()
        assert "Video with this ID already exists" in data["error"]

    @patch.dict(os.environ, {"ADMIN_TOKEN": "admin_test_token"})
    def test_update_video_success(self, client, admin_headers, app):
        """Test updating a video successfully"""
        with app.app_context():
            video = Video(
                video_id="update_video",
                title="Original Title",
                transcript_available=False,
            )
            db.session.add(video)
            db.session.commit()

        response = client.patch(
            "/admin/videos/update_video",
            headers=admin_headers,
            json={"title": "Updated Title", "transcript_available": True},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["transcript_available"] is True

    @patch.dict(os.environ, {"ADMIN_TOKEN": "admin_test_token"})
    def test_update_video_not_found(self, client, admin_headers):
        """Test updating non-existent video"""
        response = client.patch(
            "/admin/videos/nonexistent_video",
            headers=admin_headers,
            json={"title": "New Title"},
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "Video not found" in data["error"]

    @patch.dict(os.environ, {"ADMIN_TOKEN": "admin_test_token"})
    def test_delete_video_success(self, client, admin_headers, app):
        """Test deleting a video successfully"""
        with app.app_context():
            video = Video(video_id="delete_video", title="Video to Delete")
            db.session.add(video)
            db.session.commit()

        response = client.delete("/admin/videos/delete_video", headers=admin_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert "Video deleted successfully" in data["message"]

    @patch.dict(os.environ, {"ADMIN_TOKEN": "admin_test_token"})
    def test_delete_video_cascade_notes(self, client, admin_headers, app):
        """Test deleting video cascades to delete associated notes"""
        with app.app_context():
            user = User(
                username="testuser", password_hash=generate_password_hash("pass")
            )
            video = Video(video_id="cascade_video", title="Video with Notes")
            db.session.add_all([user, video])
            db.session.commit()

            # Create notes for the video
            note1 = Note(
                video_id="cascade_video",
                text="Note 1",
                timestamp="1:00",
                user_id=user.id,
            )
            note2 = Note(
                video_id="cascade_video",
                text="Note 2",
                timestamp="2:00",
                user_id=user.id,
            )
            db.session.add_all([note1, note2])
            db.session.commit()

        response = client.delete("/admin/videos/cascade_video", headers=admin_headers)

        assert response.status_code == 200

        # Verify notes were also deleted
        with app.app_context():
            remaining_notes = Note.query.filter_by(video_id="cascade_video").all()
            assert len(remaining_notes) == 0

    @patch.dict(os.environ, {"ADMIN_TOKEN": "admin_test_token"})
    def test_list_videos_success(self, client, admin_headers, app):
        """Test listing all videos"""
        with app.app_context():
            video1 = Video(
                video_id="video1", title="Video 1", transcript_available=True
            )
            video2 = Video(
                video_id="video2", title="Video 2", transcript_available=False
            )
            db.session.add_all([video1, video2])
            db.session.commit()

        response = client.get("/admin/videos", headers=admin_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2
        video_ids = {video["video_id"] for video in data}
        assert video_ids == {"video1", "video2"}

    def test_admin_auth_required(self, client, auth_headers):
        """Test that regular users cannot access admin endpoints"""
        # No ADMIN_TOKEN set, admin_required checks token against None and returns 403
        response = client.get("/admin/videos", headers=auth_headers)

        assert (
            response.status_code == 403
        )  # Invalid admin token (since no ADMIN_TOKEN set)
        data = response.get_json()
        assert "Invalid admin token" in data["error"]

    @patch.dict(os.environ, {"ADMIN_TOKEN": "admin_test_token"})
    def test_wrong_admin_token(self, client):
        """Test that wrong admin token is rejected"""
        wrong_headers = {"Authorization": "Bearer wrong_token"}
        response = client.get("/admin/videos", headers=wrong_headers)

        assert response.status_code == 403
        data = response.get_json()
        assert "Invalid admin token" in data["error"]

    def test_no_auth_header(self, client):
        """Test that requests without auth header are rejected"""
        response = client.get("/admin/videos")

        assert response.status_code == 401
        data = response.get_json()
        assert "Missing or invalid Authorization header" in data["error"]
