import pytest
import jwt
from datetime import datetime, timedelta, timezone
from vidwiz.app import create_app
from vidwiz.shared.models import User, Video, Note, db
from werkzeug.security import generate_password_hash


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


class TestUserWorkflow:
    """Integration tests for complete user workflows"""

    def test_complete_user_registration_and_login_workflow(self, client):
        """Test complete user registration and login flow"""
        # 1. Register new user
        response = client.post(
            "/user/signup",
            json={"username": "integrationuser", "password": "securepassword123"},
            content_type="application/json",
        )
        assert response.status_code == 201  # Success response

        # 2. Login with new user
        response = client.post(
            "/user/login",
            json={"username": "integrationuser", "password": "securepassword123"},
            content_type="application/json",
        )
        assert response.status_code == 200

        token_data = response.get_json()
        assert "token" in token_data
        token = token_data["token"]

        # 3. Verify token works for protected endpoints
        auth_headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/search?query=test", headers=auth_headers)
        assert response.status_code in [
            200,
            404,
        ]  # 404 if no videos found, which is expected

    def test_video_and_notes_management_workflow(self, client, app):
        """Test complete video and notes management workflow"""
        with app.app_context():
            # Setup user
            user = User(
                username="videouser", password_hash=generate_password_hash("password")
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Create auth token
            token = jwt.encode(
                {
                    "user_id": user_id,
                    "username": "videouser",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            auth_headers = {"Authorization": f"Bearer {token}"}

        # 1. Create first note (this should create the video as well)
        note_payload = {
            "video_id": "test_video_123",
            "video_title": "Learn Python Programming",
            "timestamp": "00:01:30",
            "text": "Introduction to Python basics",
        }
        response = client.post("/notes", json=note_payload, headers=auth_headers)
        assert response.status_code == 201
        note1_data = response.get_json()
        note1_id = note1_data["id"]

        # 2. Create second note for same video
        note_payload2 = {
            "video_id": "test_video_123",
            "video_title": "Learn Python Programming",
            "timestamp": "00:05:45",
            "text": "Variables and data types in Python",
        }
        response = client.post("/notes", json=note_payload2, headers=auth_headers)
        assert response.status_code == 201

        # 3. Get video details
        response = client.get("/videos/test_video_123", headers=auth_headers)
        assert response.status_code == 200
        video_data = response.get_json()
        assert video_data["video_id"] == "test_video_123"
        assert video_data["title"] == "Learn Python Programming"

        # 4. Get all notes for video
        response = client.get("/notes/test_video_123", headers=auth_headers)
        assert response.status_code == 200
        notes_data = response.get_json()
        assert len(notes_data) == 2

        # 5. Search for video
        response = client.get("/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        search_results = response.get_json()
        assert len(search_results) == 1
        assert search_results[0]["video_id"] == "test_video_123"

        # 6. Update one note with AI content
        ai_update_payload = {
            "text": "AI-generated summary: This section covers Python fundamentals including syntax and basic concepts.",
            "generated_by_ai": True,
        }
        response = client.patch(
            f"/notes/{note1_id}", json=ai_update_payload, headers=auth_headers
        )
        assert response.status_code == 200
        updated_note = response.get_json()
        assert updated_note["text"] == ai_update_payload["text"]
        assert updated_note["generated_by_ai"] is True

        # 7. Delete one note
        response = client.delete(f"/notes/{note1_id}", headers=auth_headers)
        assert response.status_code == 200

        # 8. Verify note was deleted
        response = client.get("/notes/test_video_123", headers=auth_headers)
        assert response.status_code == 200
        remaining_notes = response.get_json()
        assert len(remaining_notes) == 1
        assert remaining_notes[0]["text"] == "Variables and data types in Python"

    def test_multi_user_isolation_workflow(self, client, app):
        """Test that multiple users' data is properly isolated"""
        with app.app_context():
            # Create two users
            user1 = User(
                username="user1", password_hash=generate_password_hash("password1")
            )
            user2 = User(
                username="user2", password_hash=generate_password_hash("password2")
            )
            db.session.add_all([user1, user2])
            db.session.commit()

            # Create auth tokens
            token1 = jwt.encode(
                {
                    "user_id": 1,
                    "username": "user1",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            token2 = jwt.encode(
                {
                    "user_id": 2,
                    "username": "user2",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )

            auth_headers1 = {"Authorization": f"Bearer {token1}"}
            auth_headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 creates a note
        note_payload1 = {
            "video_id": "user1_video",
            "video_title": "User 1's Video",
            "timestamp": "00:01:00",
            "text": "User 1's note",
        }
        response = client.post("/notes", json=note_payload1, headers=auth_headers1)
        assert response.status_code == 201

        # User 2 creates a note
        note_payload2 = {
            "video_id": "user2_video",
            "video_title": "User 2's Video",
            "timestamp": "00:01:00",
            "text": "User 2's note",
        }
        response = client.post("/notes", json=note_payload2, headers=auth_headers2)
        assert response.status_code == 201

        # User 1 searches - should only see their video
        response = client.get("/search?query=Video", headers=auth_headers1)
        assert response.status_code == 200
        user1_results = response.get_json()
        assert len(user1_results) == 1
        assert user1_results[0]["video_title"] == "User 1's Video"

        # User 2 searches - should only see their video
        response = client.get("/search?query=Video", headers=auth_headers2)
        assert response.status_code == 200
        user2_results = response.get_json()
        assert len(user2_results) == 1
        assert user2_results[0]["video_title"] == "User 2's Video"

        # User 1 tries to access User 2's video - should succeed because videos are public
        response = client.get("/videos/user2_video", headers=auth_headers1)
        assert response.status_code == 200

        # User 2 tries to access User 1's video - should succeed because videos are public
        response = client.get("/videos/user1_video", headers=auth_headers2)
        assert response.status_code == 200

    def test_error_handling_workflow(self, client, app):
        """Test various error scenarios in workflows"""
        with app.app_context():
            user = User(
                username="erroruser", password_hash=generate_password_hash("password")
            )
            db.session.add(user)
            db.session.commit()

            token = jwt.encode(
                {
                    "user_id": 1,
                    "username": "erroruser",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            auth_headers = {"Authorization": f"Bearer {token}"}

        # 1. Try to create note with invalid data
        invalid_payload = {
            "video_id": "",  # Empty video_id
            "video_title": "Test Video",
            "timestamp": "invalid_timestamp",
            "text": "Test note",
        }
        response = client.post("/notes", json=invalid_payload, headers=auth_headers)
        assert response.status_code == 400

        # 2. Try to access non-existent video
        response = client.get("/videos/nonexistent", headers=auth_headers)
        assert response.status_code == 404

        # 3. Try to delete non-existent note
        response = client.delete("/note/99999", headers=auth_headers)
        assert response.status_code == 404

        # 4. Try to update non-existent note
        response = client.patch(
            "/note/99999", json={"ai_note": "test"}, headers=auth_headers
        )
        assert response.status_code == 404

        # 5. Try to access protected endpoints without auth
        response = client.get("/search?query=test")
        assert response.status_code == 401

        response = client.get("/videos/test")
        assert response.status_code == 401

        response = client.get("/notes/test")
        assert response.status_code == 401

    def test_large_scale_data_workflow(self, client, app):
        """Test workflow with larger amounts of data"""
        with app.app_context():
            user = User(
                username="bulkuser", password_hash=generate_password_hash("password")
            )
            db.session.add(user)
            db.session.commit()

            token = jwt.encode(
                {
                    "user_id": 1,
                    "username": "bulkuser",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            auth_headers = {"Authorization": f"Bearer {token}"}

        # Create multiple videos with multiple notes each
        video_count = 5
        notes_per_video = 10

        for video_idx in range(video_count):
            video_id = f"bulk_video_{video_idx}"
            video_title = f"Bulk Test Video {video_idx}"

            for note_idx in range(notes_per_video):
                timestamp = f"00:{note_idx:02d}:00"
                note_payload = {
                    "video_id": video_id,
                    "video_title": video_title,
                    "timestamp": timestamp,
                    "text": f"Note {note_idx} for video {video_idx}",
                }
                response = client.post(
                    "/notes", json=note_payload, headers=auth_headers
                )
                assert response.status_code == 201

        # Test searching across all videos
        response = client.get("/search?query=Bulk", headers=auth_headers)
        assert response.status_code == 200
        search_results = response.get_json()
        assert len(search_results) == video_count

        # Test getting notes for each video
        for video_idx in range(video_count):
            video_id = f"bulk_video_{video_idx}"
            response = client.get(f"/notes/{video_id}", headers=auth_headers)
            assert response.status_code == 200
            notes = response.get_json()
            assert len(notes) == notes_per_video

        # Test getting video details for each video
        for video_idx in range(video_count):
            video_id = f"bulk_video_{video_idx}"
            response = client.get(f"/videos/{video_id}", headers=auth_headers)
            assert response.status_code == 200
            video_data = response.get_json()
            assert video_data["video_id"] == video_id

    def test_authentication_edge_cases_workflow(self, client, app):
        """Test various authentication edge cases in workflows"""
        with app.app_context():
            user = User(
                username="authuser", password_hash=generate_password_hash("password")
            )
            db.session.add(user)
            db.session.commit()

        # 1. Test with expired token
        expired_token = jwt.encode(
            {
                "user_id": 1,
                "username": "authuser",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        expired_headers = {"Authorization": f"Bearer {expired_token}"}

        response = client.get("/search?query=test", headers=expired_headers)
        assert response.status_code == 401

        # 2. Test with invalid signature
        invalid_token = jwt.encode(
            {
                "user_id": 1,
                "username": "authuser",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "wrong_secret",
            algorithm="HS256",
        )
        invalid_headers = {"Authorization": f"Bearer {invalid_token}"}

        response = client.get("/search?query=test", headers=invalid_headers)
        assert response.status_code == 401

        # 3. Test with malformed token
        malformed_headers = {"Authorization": "Bearer not.a.valid.jwt.token"}
        response = client.get("/search?query=test", headers=malformed_headers)
        assert response.status_code == 401

        # 4. Test with missing Bearer prefix
        no_bearer_headers = {"Authorization": "SomeToken"}
        response = client.get("/search?query=test", headers=no_bearer_headers)
        assert response.status_code == 401

        # 5. Test with valid token but wrong user_id
        token_wrong_user = jwt.encode(
            {
                "user_id": 99999,
                "username": "nonexistent",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        wrong_user_headers = {"Authorization": f"Bearer {token_wrong_user}"}

        # This should work for search (user isolation is handled at data level)
        response = client.get("/search?query=test", headers=wrong_user_headers)
        assert response.status_code in [200, 404]  # 404 if no videos found


class TestDataConsistency:
    """Tests for data consistency and integrity"""

    def test_cascade_delete_consistency(self, client, app):
        """Test that cascade deletes work correctly"""
        with app.app_context():
            user = User(
                username="deleteuser", password_hash=generate_password_hash("password")
            )
            db.session.add(user)
            db.session.commit()

            # Create video and notes
            video = Video(video_id="delete_test", title="Delete Test Video")
            db.session.add(video)
            db.session.commit()

            note1 = Note(
                video_id="delete_test", timestamp="00:01:00", text="Note 1", user_id=1
            )
            note2 = Note(
                video_id="delete_test", timestamp="00:02:00", text="Note 2", user_id=1
            )
            db.session.add_all([note1, note2])
            db.session.commit()

            note1_id = note1.id
            note2_id = note2.id

            # Delete video
            db.session.delete(video)
            db.session.commit()

            # Verify notes were cascade deleted
            assert db.session.get(Note, note1_id) is None
            assert db.session.get(Note, note2_id) is None


class TestPerformance:
    """Basic performance and scalability tests"""

    def test_search_performance_with_many_videos(self, client, app):
        """Test search performance with many videos"""
        with app.app_context():
            user = User(
                username="perfuser", password_hash=generate_password_hash("password")
            )
            db.session.add(user)
            db.session.commit()

            # Create many videos
            videos = []
            for i in range(100):
                video = Video(
                    video_id=f"perf_video_{i}",
                    title=f"Performance Test Video {i}",
                )
                videos.append(video)

            db.session.add_all(videos)
            db.session.commit()

            # Add at least one note to each video so they appear in search
            notes = []
            for i in range(100):
                note = Note(
                    video_id=f"perf_video_{i}",
                    timestamp="00:01:00",
                    text=f"Performance note {i}",
                    user_id=1,
                )
                notes.append(note)

            db.session.add_all(notes)
            db.session.commit()

            token = jwt.encode(
                {
                    "user_id": 1,
                    "username": "perfuser",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            auth_headers = {"Authorization": f"Bearer {token}"}

        # Search should still be fast
        response = client.get("/search?query=Performance", headers=auth_headers)
        assert response.status_code == 200
        results = response.get_json()
        assert len(results) == 100


class TestAPIConsistency:
    """Test API consistency and data integrity across endpoints"""

    def test_note_creation_and_video_retrieval_consistency(self, client, app):
        """Test that creating notes and retrieving videos maintains consistency"""
        with app.app_context():
            # Create user
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            # Create JWT token
            token = jwt.encode(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            auth_headers = {"Authorization": f"Bearer {token}"}

        # Create note (should create video automatically)
        payload = {
            "video_id": "vid123",
            "video_title": "Auto-created Video",
            "timestamp": "1:23",
            "text": "Test note",
        }
        response = client.post("/notes", json=payload, headers=auth_headers)
        assert response.status_code == 201

        # Retrieve video via video endpoint
        response = client.get("/videos/vid123", headers=auth_headers)
        assert response.status_code == 200
        video_data = response.get_json()
        assert video_data["title"] == "Auto-created Video"

        # Retrieve notes via notes endpoint
        response = client.get("/notes/vid123", headers=auth_headers)
        assert response.status_code == 200
        notes_data = response.get_json()
        assert len(notes_data) == 1
        assert notes_data[0]["text"] == "Test note"

    def test_cross_endpoint_user_isolation(self, client, app):
        """Test that user isolation is maintained across all endpoints"""
        with app.app_context():
            # Create two users
            user1 = User(username="user1", password_hash="hash1")
            user2 = User(username="user2", password_hash="hash2")
            db.session.add_all([user1, user2])
            db.session.commit()

            # Create tokens for both users
            token1 = jwt.encode(
                {
                    "user_id": user1.id,
                    "username": user1.username,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            token2 = jwt.encode(
                {
                    "user_id": user2.id,
                    "username": user2.username,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            auth_headers1 = {"Authorization": f"Bearer {token1}"}
            auth_headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 creates a note
        payload = {
            "video_id": "private_vid",
            "video_title": "Private Video",
            "timestamp": "1:23",
            "text": "Private note",
        }
        response = client.post("/notes", json=payload, headers=auth_headers1)
        assert response.status_code == 201
        note_id = response.get_json()["id"]

        # User 2 tries to access User 1's video - should succeed because videos are public
        response = client.get("/videos/private_vid", headers=auth_headers2)
        assert response.status_code == 200

        # User 2 tries to access User 1's notes - should get empty list
        response = client.get("/notes/private_vid", headers=auth_headers2)
        assert response.status_code == 200
        assert response.get_json() == []

        # User 2 tries to delete User 1's note - should fail
        response = client.delete(f"/notes/{note_id}", headers=auth_headers2)
        assert response.status_code == 404

        # User 2 tries to update User 1's note - should fail
        response = client.patch(
            f"/notes/{note_id}",
            json={"text": "Hacked note", "generated_by_ai": False},
            headers=auth_headers2,
        )
        assert response.status_code == 404

    def test_concurrent_operations_data_integrity(self, client, app):
        """Test data integrity during concurrent-like operations"""
        with app.app_context():
            # Create user
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            token = jwt.encode(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            auth_headers = {"Authorization": f"Bearer {token}"}

        # Create multiple notes for the same video rapidly
        video_id = "concurrent_vid"
        note_ids = []

        for i in range(10):
            payload = {
                "video_id": video_id,
                "video_title": f"Video {i}"
                if i == 0
                else None,  # Only provide title once
                "timestamp": f"0:{i:02d}",
                "text": f"Note {i}",
            }
            response = client.post("/notes", json=payload, headers=auth_headers)
            assert response.status_code == 201
            note_ids.append(response.get_json()["id"])

        # Verify all notes were created
        response = client.get(f"/notes/{video_id}", headers=auth_headers)
        assert response.status_code == 200
        notes = response.get_json()
        assert len(notes) == 10

        # Verify video was created only once
        response = client.get(f"/videos/{video_id}", headers=auth_headers)
        assert response.status_code == 200
        video = response.get_json()
        assert video["title"] == "Video 0"  # Should use title from first note creation

        # Clean up by deleting all notes
        for note_id in note_ids:
            response = client.delete(f"/notes/{note_id}", headers=auth_headers)
            assert response.status_code == 200

        # Verify all notes are deleted
        response = client.get(f"/notes/{video_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json() == []
