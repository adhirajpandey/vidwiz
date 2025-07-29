import pytest
import jwt
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
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
def sample_user(app):
    """Create a sample user for testing"""
    with app.app_context():
        user = User(
            username="testuser", password_hash=generate_password_hash("testpassword")
        )
        db.session.add(user)
        db.session.commit()
        return user


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


class TestVideoPageRoute:
    def test_video_page_with_auth(self, client, auth_headers):
        """Test video page with valid authentication"""
        response = client.get("/dashboard/test_video_id", headers=auth_headers)
        assert response.status_code == 200
        # Check if it returns HTML content
        assert b"html" in response.data.lower() or response.mimetype == "text/html"

    def test_video_page_without_auth(self, client):
        """Test video page without authentication"""
        response = client.get("/dashboard/test_video_id")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
        assert "Authorization" in data["error"]


class TestSearchRoute:
    def test_search_with_results(self, client, auth_headers, app):
        """Test search with matching results"""
        with app.app_context():
            # Create test data
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid1", title="Python Tutorial", user_id=1)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid1", timestamp="00:01:30", text="Test note", user_id=1
            )
            db.session.add(note)
            db.session.commit()

        response = client.get("/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["video_id"] == "vid1"
        assert data[0]["video_title"] == "Python Tutorial"

    def test_search_no_results(self, client, auth_headers, app):
        """Test search with no matching results"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid1", title="Java Tutorial", user_id=1)
            db.session.add(video)
            db.session.commit()

        response = client.get("/search?query=Python", headers=auth_headers)
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "No videos found matching the query"

    def test_search_missing_query_parameter(self, client, auth_headers):
        """Test search without query parameter"""
        response = client.get("/search", headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Query parameter is required"

    def test_search_without_auth(self, client):
        """Test search without authentication"""
        response = client.get("/search?query=Python")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_search_case_insensitive(self, client, auth_headers, app):
        """Test search is case insensitive"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid1", title="Python Tutorial", user_id=1)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid1", timestamp="00:01:30", text="Test note", user_id=1
            )
            db.session.add(note)
            db.session.commit()

        # Test lowercase query
        response = client.get("/search?query=python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

        # Test uppercase query
        response = client.get("/search?query=PYTHON", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1

    def test_search_partial_match(self, client, auth_headers, app):
        """Test search with partial title match"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            video = Video(
                video_id="vid1", title="Advanced Python Programming", user_id=1
            )
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid1", timestamp="00:01:30", text="Test note", user_id=1
            )
            db.session.add(note)
            db.session.commit()

        response = client.get("/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert "Python" in data[0]["video_title"]

    def test_search_only_videos_with_notes(self, client, auth_headers, app):
        """Test search only returns videos that have notes"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

            # Video with notes
            video_with_notes = Video(
                video_id="vid1", title="Python Tutorial", user_id=1
            )
            db.session.add(video_with_notes)

            # Video without notes
            video_without_notes = Video(
                video_id="vid2", title="Python Advanced", user_id=1
            )
            db.session.add(video_without_notes)

            db.session.commit()

            # Add note only to first video
            note = Note(
                video_id="vid1", timestamp="00:01:30", text="Test note", user_id=1
            )
            db.session.add(note)
            db.session.commit()

        response = client.get("/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1  # Only video with notes should be returned
        assert data[0]["video_id"] == "vid1"

    def test_search_user_isolation(self, client, auth_headers, app):
        """Test search only returns videos belonging to the authenticated user"""
        with app.app_context():
            # Create two users
            user1 = User(username="user1", password_hash="hashed")
            user2 = User(username="user2", password_hash="hashed")
            db.session.add_all([user1, user2])
            db.session.commit()

            # Create videos for different users
            video1 = Video(video_id="vid1", title="Python Tutorial", user_id=1)
            video2 = Video(video_id="vid2", title="Python Advanced", user_id=2)
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
        response = client.get("/search?query=Python", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1  # Only user 1's video should be returned
        assert data[0]["video_id"] == "vid1"


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
            "/signup",
            data={"username": "newuser", "password": "newpassword"},
            follow_redirects=False,
        )

        # Should redirect to login page
        assert response.status_code == 302
        assert "/login" in response.location

    def test_signup_missing_username(self, client):
        """Test signup with missing username"""
        response = client.post("/signup", data={"password": "newpassword"})
        assert response.status_code == 200
        # Should return signup page with error
        assert b"Username and password required" in response.data

    def test_signup_missing_password(self, client):
        """Test signup with missing password"""
        response = client.post("/signup", data={"username": "newuser"})
        assert response.status_code == 200
        assert b"Username and password required" in response.data

    def test_signup_duplicate_username(self, client, sample_user):
        """Test signup with existing username"""
        response = client.post(
            "/signup",
            data={
                "username": "testuser",  # Username from sample_user fixture
                "password": "newpassword",
            },
        )
        assert response.status_code == 200
        assert b"Username already exists" in response.data


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
            "/login",
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
            "/login", json={"password": "testpassword"}, content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Username and password required."

    def test_login_missing_password(self, client):
        """Test login with missing password"""
        response = client.post(
            "/login", json={"username": "testuser"}, content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Username and password required."

    def test_login_invalid_username(self, client):
        """Test login with invalid username"""
        response = client.post(
            "/login",
            json={"username": "nonexistent", "password": "testpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid username or password."

    def test_login_invalid_password(self, client, sample_user):
        """Test login with invalid password"""
        response = client.post(
            "/login",
            json={"username": "testuser", "password": "wrongpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid username or password."

    def test_login_empty_credentials(self, client):
        """Test login with empty credentials"""
        response = client.post(
            "/login",
            json={"username": "", "password": ""},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Username and password required."


class TestLogoutRoute:
    def test_logout(self, client):
        """Test logout route"""
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

        # Check that cookie is cleared
        assert "jwt_token=" in response.headers.get("Set-Cookie", "")
        assert "Expires=" in response.headers.get("Set-Cookie", "")
