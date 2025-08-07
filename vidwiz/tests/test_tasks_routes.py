import jwt
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from vidwiz.shared.models import User, Video, Task, TaskStatus, db
from vidwiz.shared.config import FETCH_TRANSCRIPT_TASK_TYPE
from werkzeug.security import generate_password_hash


class TestTasksRoutes:
    """Test basic tasks routes functionality"""

    def test_get_transcript_task_success(self, client, auth_headers, app, sample_user):
        """Test successfully retrieving a transcript task"""
        with app.app_context():
            # Create a pending transcript task
            task = Task(
                task_type=FETCH_TRANSCRIPT_TASK_TYPE,
                status=TaskStatus.PENDING,
                task_details={"video_id": "test_video_123"},
                retry_count=0,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.get("/tasks/transcript", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["task_id"] == task_id
        assert data["task_type"] == FETCH_TRANSCRIPT_TASK_TYPE
        assert data["task_details"]["video_id"] == "test_video_123"
        assert data["retry_count"] == 1  # Should increment

        # Verify task status was updated
        with app.app_context():
            updated_task = db.session.get(Task, task_id)
            assert updated_task.status == TaskStatus.IN_PROGRESS

    def test_get_transcript_task_no_tasks_timeout(self, client, auth_headers):
        """Test timeout when no tasks available"""
        response = client.get("/tasks/transcript?timeout=1", headers=auth_headers)

        assert response.status_code == 204
        # Note: 204 responses have no content, so no JSON to parse

    def test_submit_transcript_result_success(
        self, client, auth_headers, app, sample_user
    ):
        """Test successfully submitting a transcript result"""
        with app.app_context():
            # Create an in-progress task
            task = Task(
                task_type=FETCH_TRANSCRIPT_TASK_TYPE,
                status=TaskStatus.IN_PROGRESS,
                task_details={"video_id": "success_video"},
                retry_count=1,
                worker_details={"worker_user_id": 1},
            )
            video = Video(
                video_id="success_video",
                title="Success Video",
                transcript_available=False,
            )
            db.session.add_all([task, video])
            db.session.commit()
            task_id = task.id

        with patch("vidwiz.routes.tasks_routes.store_transcript_in_s3"):
            response = client.post(
                "/tasks/transcript",
                headers=auth_headers,
                json={
                    "task_id": task_id,
                    "video_id": "success_video",
                    "success": True,
                    "transcript": [
                        {"text": "This is the transcript content", "start": 0, "end": 5}
                    ],
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert "successfully" in data["message"]
            assert data["status"] == "completed"  # API returns lowercase enum values

    def test_submit_transcript_result_failure_retry(
        self, client, auth_headers, app, sample_user
    ):
        """Test submitting a failed result that can be retried"""
        with app.app_context():
            task = Task(
                task_type=FETCH_TRANSCRIPT_TASK_TYPE,
                status=TaskStatus.IN_PROGRESS,
                task_details={"video_id": "retry_video"},
                retry_count=1,
                worker_details={"worker_user_id": 1},
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.post(
            "/tasks/transcript",
            headers=auth_headers,
            json={
                "task_id": task_id,
                "video_id": "retry_video",
                "success": False,
                "error_message": "Network timeout",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"  # Should be reset for retry

    def test_submit_transcript_result_wrong_worker(self, client, app):
        """Test submitting result from wrong worker fails"""
        with app.app_context():
            # Create users
            user1 = User(username="user1", password_hash=generate_password_hash("pass"))
            user2 = User(username="user2", password_hash=generate_password_hash("pass"))
            db.session.add_all([user1, user2])
            db.session.commit()

            task = Task(
                task_type=FETCH_TRANSCRIPT_TASK_TYPE,
                status=TaskStatus.IN_PROGRESS,
                task_details={"video_id": "wrong_worker_video"},
                retry_count=1,
                worker_details={"worker_user_id": user1.id},  # Assigned to user1
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

            # Create token for user2
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

        response = client.post(
            "/tasks/transcript",
            headers=headers,
            json={
                "task_id": task_id,
                "video_id": "wrong_worker_video",
                "success": True,
            },
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "different worker" in data["error"]

    def test_get_transcript_task_no_auth(self, client):
        """Test getting transcript task without authentication"""
        response = client.get("/tasks/transcript")

        assert response.status_code == 401

    def test_submit_transcript_result_no_auth(self, client):
        """Test submitting result without authentication"""
        response = client.post(
            "/tasks/transcript",
            json={"task_id": 1, "video_id": "test_video", "success": True},
        )

        assert response.status_code == 401

    @patch.dict(os.environ, {"ADMIN_TOKEN": "admin_test_token"})
    def test_admin_can_get_tasks(self, client, admin_headers, app):
        """Test that admin can also get transcript tasks"""
        with app.app_context():
            task = Task(
                task_type=FETCH_TRANSCRIPT_TASK_TYPE,
                status=TaskStatus.PENDING,
                task_details={"video_id": "admin_video"},
                retry_count=0,
            )
            db.session.add(task)
            db.session.commit()

        response = client.get("/tasks/transcript", headers=admin_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["task_details"]["video_id"] == "admin_video"
