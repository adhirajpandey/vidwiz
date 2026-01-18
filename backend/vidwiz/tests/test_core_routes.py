import jwt
from vidwiz.shared.models import User, Video, Note, db

# Test constants
TEST_VIDEO_ID = "vid1"
TEST_VIDEO_TITLE = "Python Tutorial"
TEST_NOTE_TEXT = "Test note"
TEST_TIMESTAMP = "00:01:30"


class TestIndexRoute:
    def test_index_route(self, client):
        """Test the landing page route"""
        response = client.get("/")
        assert response.status_code == 200
        # Check if it returns HTML content
        assert b"html" in response.data.lower() or response.mimetype == "text/html"


class TestDashboardRoute:
    def test_dashboard_route(self, client):
        """Test the dashboard page route"""
        response = client.get("/dashboard")
        assert response.status_code == 200
        # Check if it returns HTML content
        assert b"html" in response.data.lower() or response.mimetype == "text/html"


class TestSearchRoute:
    def test_search_with_results(self, client, auth_headers, app):
        """Test search with matching results"""
        with app.app_context():
            # Create test data
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id=TEST_VIDEO_ID, title=TEST_VIDEO_TITLE)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id=TEST_VIDEO_ID,
                timestamp=TEST_TIMESTAMP,
                text=TEST_NOTE_TEXT,
                user_id=1,
            )
            db.session.add(note)
            db.session.commit()

        response = client.get("/api/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "videos" in data
        assert len(data["videos"]) == 1
        assert data["videos"][0]["video_id"] == TEST_VIDEO_ID
        assert data["videos"][0]["video_title"] == TEST_VIDEO_TITLE

    def test_search_no_results(self, client, auth_headers, app):
        """Test search with no matching results"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid1", title="Java Tutorial")
            db.session.add(video)
            db.session.commit()

        response = client.get("/api/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["videos"] == []
        assert data["total"] == 0

    def test_search_missing_query_parameter(self, client, auth_headers):
        """Test search without query parameter"""
        response = client.get("/api/search", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        # Empty query returns all videos with user's notes
        assert "videos" in data

    def test_search_without_auth(self, client):
        """Test search without authentication"""
        response = client.get("/api/search?query=Python")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_search_case_insensitive(self, client, auth_headers, app):
        """Test search is case insensitive"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid1", title="Python Tutorial")
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid1", timestamp="00:01:30", text="Test note", user_id=1
            )
            db.session.add(note)
            db.session.commit()

        # Test lowercase query
        response = client.get("/api/search?query=python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["videos"]) == 1

        # Test uppercase query
        response = client.get("/api/search?query=PYTHON", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["videos"]) == 1

    def test_search_partial_match(self, client, auth_headers, app):
        """Test search with partial title match"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid1", title="Advanced Python Programming")
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid1", timestamp="00:01:30", text="Test note", user_id=1
            )
            db.session.add(note)
            db.session.commit()

        response = client.get("/api/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["videos"]) == 1
        assert "Python" in data["videos"][0]["video_title"]

    def test_search_only_videos_with_notes(self, client, auth_headers, app):
        """Test search only returns videos that have notes"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            # Video with notes
            video_with_notes = Video(video_id="vid1", title="Python Tutorial")
            db.session.add(video_with_notes)

            # Video without notes
            video_without_notes = Video(video_id="vid2", title="Python Advanced")
            db.session.add(video_without_notes)

            db.session.commit()

            # Add note only to first video
            note = Note(
                video_id="vid1", timestamp="00:01:30", text="Test note", user_id=1
            )
            db.session.add(note)
            db.session.commit()

        response = client.get("/api/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["videos"]) == 1  # Only video with notes should be returned
        assert data["videos"][0]["video_id"] == "vid1"

    def test_search_user_isolation(self, client, auth_headers, app):
        """Test search only returns videos belonging to the authenticated user"""
        with app.app_context():
            # Create two users
            user1 = User(username="user1", password_hash="hashed")
            user2 = User(username="user2", password_hash="hashed")
            db.session.add_all([user1, user2])
            db.session.commit()

            # Create videos for different users
            video1 = Video(video_id="vid1", title="Python Tutorial")
            video2 = Video(video_id="vid2", title="Python Advanced")
            db.session.add_all([video1, video2])
            db.session.commit()

            # Add notes to both videos
            note1 = Note(
                video_id="vid1", timestamp="00:01:30", text="Note 1", user_id=1
            )
            note2 = Note(
                video_id="vid2", timestamp="00:01:30", text="Note 2", user_id=2
            )
            db.session.add_all([note1, note2])
            db.session.commit()

        # Search as user 1 (from auth_headers fixture)
        response = client.get("/api/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["videos"]) == 1  # Only user 1's video should be returned
        assert data["videos"][0]["video_id"] == "vid1"


class TestSignupRoute:
    def test_signup_get_request(self, client):
        """Test GET request to signup page"""
        response = client.get("/signup")
        assert response.status_code == 200
        # Check if it returns HTML content
        assert b"html" in response.data.lower() or response.mimetype == "text/html"

    def test_signup_post_success(self, client):
        """Test successful user signup"""
        response = client.post(
            "/api/user/signup",
            json={"username": "newuser", "password": "newpassword"},
            content_type="application/json",
        )

        # Should return success message
        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "User created successfully"

    def test_signup_missing_username(self, client):
        """Test signup with missing username"""
        response = client.post(
            "/api/user/signup",
            json={"password": "newpassword"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid data" in data["error"]

    def test_signup_missing_password(self, client):
        """Test signup with missing password"""
        response = client.post(
            "/api/user/signup",
            json={"username": "newuser"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid data" in data["error"]

    def test_signup_duplicate_username(self, client, sample_user):
        """Test signup with existing username"""
        response = client.post(
            "/api/user/signup",
            json={
                "username": "testuser",  # Username from sample_user fixture
                "password": "newpassword",
            },
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Username already exists."


class TestLoginRoute:
    def test_login_get_request(self, client):
        """Test GET request to login page"""
        response = client.get("/login")
        assert response.status_code == 200
        # Check if it returns HTML content
        assert b"html" in response.data.lower() or response.mimetype == "text/html"

    def test_login_post_success(self, client, sample_user):
        """Test successful login"""
        response = client.post(
            "/api/user/login",
            json={"username": "testuser", "password": "testpassword"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data

        # Verify token is valid
        token = data["token"]
        with client.application.app_context():
            payload = jwt.decode(
                token, client.application.config["SECRET_KEY"], algorithms=["HS256"]
            )
            assert payload["username"] == "testuser"
            # Check that user_id is a positive integer (don't rely on detached instance)
            assert isinstance(payload["user_id"], int) and payload["user_id"] > 0

    def test_login_missing_username(self, client):
        """Test login with missing username"""
        response = client.post(
            "/api/user/login",
            json={"password": "testpassword"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid data" in data["error"]

    def test_login_missing_password(self, client):
        """Test login with missing password"""
        response = client.post(
            "/api/user/login",
            json={"username": "testuser"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid data" in data["error"]

    def test_login_invalid_username(self, client):
        """Test login with invalid username"""
        response = client.post(
            "/api/user/login",
            json={"username": "nonexistent", "password": "testpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid username or password."

    def test_login_invalid_password(self, client, sample_user):
        """Test login with invalid password"""
        response = client.post(
            "/api/user/login",
            json={"username": "testuser", "password": "wrongpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid username or password."

    def test_login_empty_credentials(self, client):
        """Test login with empty credentials"""
        response = client.post(
            "/api/user/login",
            json={"username": "", "password": ""},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid data" in data["error"]



