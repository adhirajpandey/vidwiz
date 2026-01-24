import jwt
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from vidwiz.shared.models import User, Video, Task, TaskStatus, db
from vidwiz.shared.config import FETCH_TRANSCRIPT_TASK_TYPE, FETCH_METADATA_TASK_TYPE
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

        response = client.get("/api/tasks/transcript", headers=auth_headers)

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
        response = client.get("/api/tasks/transcript?timeout=1", headers=auth_headers)

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
                "/api/tasks/transcript",
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
            "/api/tasks/transcript",
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
            user1 = User(email="user1@example.com", name="User One", password_hash=generate_password_hash("pass"))
            user2 = User(email="user2@example.com", name="User Two", password_hash=generate_password_hash("pass"))
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
                    "email": "user2@example.com",
                    "name": "User Two",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/tasks/transcript",
            headers=headers,
            json={
                "task_id": task_id,
                "video_id": "wrong_worker_video",
                "success": True,
            },
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "different worker" in data["error"]["message"]

    def test_get_transcript_task_no_auth(self, client):
        """Test getting transcript task without authentication"""
        response = client.get("/api/tasks/transcript")

        assert response.status_code == 401

    def test_submit_transcript_result_no_auth(self, client):
        """Test submitting result without authentication"""
        response = client.post(
            "/api/tasks/transcript",
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

        response = client.get("/api/tasks/transcript", headers=admin_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["task_details"]["video_id"] == "admin_video"

    # New tests for metadata tasks and increased coverage

    def test_get_metadata_task_success(self, client, auth_headers, app, sample_user):
        """Test successfully retrieving a metadata task"""
        with app.app_context():
            task = Task(
                task_type=FETCH_METADATA_TASK_TYPE,
                status=TaskStatus.PENDING,
                task_details={"video_id": "meta_video"},
                retry_count=0,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.get("/api/tasks/metadata", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["task_id"] == task_id
        assert data["task_type"] == FETCH_METADATA_TASK_TYPE

        with app.app_context():
            updated_task = db.session.get(Task, task_id)
            assert updated_task.status == TaskStatus.IN_PROGRESS

    def test_get_metadata_task_timeout(self, client, auth_headers):
        """Test timeout for metadata tasks"""
        response = client.get("/api/tasks/metadata?timeout=1", headers=auth_headers)
        assert response.status_code == 204

    def test_submit_metadata_result_success(self, client, auth_headers, app, sample_user):
        """Test submitting successful metadata result"""
        with app.app_context():
            video = Video(video_id="meta_video", title="Meta Video")
            task = Task(
                task_type=FETCH_METADATA_TASK_TYPE,
                status=TaskStatus.IN_PROGRESS,
                task_details={"video_id": "meta_video"},
                worker_details={"worker_user_id": 1},
            )
            db.session.add_all([video, task])
            db.session.commit()
            task_id = task.id

        metadata = {"title": "New Title", "duration": 100}
        response = client.post(
            "/api/tasks/metadata",
            headers=auth_headers,
            json={
                "task_id": task_id,
                "video_id": "meta_video",
                "success": True,
                "metadata": metadata
            }
        )
        assert response.status_code == 200

        with app.app_context():
            updated_video = Video.query.filter_by(video_id="meta_video").first()
            assert updated_video.video_metadata == metadata
            updated_task = db.session.get(Task, task_id)
            assert updated_task.status == TaskStatus.COMPLETED

    def test_submit_metadata_result_failure_retry(self, client, auth_headers, app, sample_user):
        """Test submitting failed metadata result for retry"""
        with app.app_context():
            task = Task(
                task_type=FETCH_METADATA_TASK_TYPE,
                status=TaskStatus.IN_PROGRESS,
                task_details={"video_id": "meta_video"},
                worker_details={"worker_user_id": 1},
                retry_count=0
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.post(
            "/api/tasks/metadata",
            headers=auth_headers,
            json={
                "task_id": task_id,
                "video_id": "meta_video",
                "success": False,
                "error_message": "Failed to fetch"
            }
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"

    def test_submit_metadata_result_task_not_found(self, client, auth_headers):
        """Test submitting result for non-existent task"""
        response = client.post(
            "/api/tasks/metadata",
            headers=auth_headers,
            json={
                "task_id": 9999,
                "video_id": "meta_video",
                "success": True
            }
        )
        assert response.status_code == 404

    def test_submit_metadata_result_video_mismatch(self, client, auth_headers, app, sample_user):
        """Test submitting result with video id mismatch"""
        with app.app_context():
            task = Task(
                task_type=FETCH_METADATA_TASK_TYPE,
                status=TaskStatus.IN_PROGRESS,
                task_details={"video_id": "meta_video"},
                worker_details={"worker_user_id": 1},
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.post(
            "/api/tasks/metadata",
            headers=auth_headers,
            json={
                "task_id": task_id,
                "video_id": "wrong_video",
                "success": True
            }
        )
        assert response.status_code == 400
        assert "mismatch" in response.get_json()["error"]["message"]

    def test_submit_transcript_result_task_not_in_progress(self, client, auth_headers, app, sample_user):
        """Test submitting result for task not in progress"""
        with app.app_context():
            task = Task(
                task_type=FETCH_TRANSCRIPT_TASK_TYPE,
                status=TaskStatus.PENDING,
                task_details={"video_id": "test_video"},
                worker_details={"worker_user_id": 1},
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        response = client.post(
            "/api/tasks/transcript",
            headers=auth_headers,
            json={
                "task_id": task_id,
                "video_id": "test_video",
                "success": True
            }
        )
        assert response.status_code == 400
        assert "not in progress" in response.get_json()["error"]["message"]
