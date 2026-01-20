"""
Common test fixtures used across multiple test files.
This file reduces duplication by centralizing shared fixtures.
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from vidwiz.app import create_app
from vidwiz.shared.models import User, Video, db

# Test constants
TEST_SECRET_KEY = "test_secret_key"
ADMIN_TEST_TOKEN = "admin_test_token"
DEFAULT_USER_ID = 1
DEFAULT_EMAIL = "testuser@example.com"
DEFAULT_NAME = "Test User"
DEFAULT_PASSWORD = "testpassword"


@pytest.fixture
def app():
    """Create and configure a test Flask application with all required config keys"""
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": TEST_SECRET_KEY,
            "JWT_EXPIRY_HOURS": 24,
            "DB_URL": "sqlite:///:memory:",
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_REGION": "us-test-1",
            "SQS_QUEUE_URL": "http://localhost/mock-sqs",
            "S3_BUCKET_NAME": "test-bucket",
            "ADMIN_TOKEN": ADMIN_TEST_TOKEN,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application"""
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Create auth headers with valid JWT token for default user"""
    with app.app_context():
        token = jwt.encode(
            {
                "user_id": DEFAULT_USER_ID,
                "email": DEFAULT_EMAIL,
                "name": DEFAULT_NAME,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    """Create admin headers with valid admin token"""
    return {"Authorization": f"Bearer {ADMIN_TEST_TOKEN}"}


@pytest.fixture
def sample_user(app):
    """Create a sample user for testing"""
    with app.app_context():
        user = User(
            email=DEFAULT_EMAIL,
            name=DEFAULT_NAME,
            password_hash=generate_password_hash(DEFAULT_PASSWORD),
        )
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def sample_video(app):
    """Create a sample video for testing"""
    with app.app_context():
        video = Video(
            video_id="test_video_123",
            title="Test Video Title",
            transcript_available=True,
        )
        db.session.add(video)
        db.session.commit()
        return video


@pytest.fixture
def auth_headers_user2(app):
    """Create auth headers for second user"""
    with app.app_context():
        token = jwt.encode(
            {
                "user_id": 2,
                "email": "testuser2@example.com",
                "name": "Test User 2",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_users(app):
    """Create multiple sample users for testing"""
    with app.app_context():
        user1 = User(
            email=DEFAULT_EMAIL,
            name=DEFAULT_NAME,
            password_hash=generate_password_hash(DEFAULT_PASSWORD),
        )
        user2 = User(
            email="testuser2@example.com",
            name="Test User 2",
            password_hash=generate_password_hash("testpass2"),
        )
        db.session.add_all([user1, user2])
        db.session.commit()
        return [user1, user2]


@pytest.fixture
def sample_videos(app):
    """Create multiple sample videos for testing"""
    with app.app_context():
        videos = [
            Video(video_id="vid123", title="Test Video 1", transcript_available=True),
            Video(video_id="vid456", title="Test Video 2", transcript_available=False),
            Video(video_id="vid789", title="Test Video 3", transcript_available=True),
        ]
        db.session.add_all(videos)
        db.session.commit()
        return videos


def create_jwt_token(app, user_id=DEFAULT_USER_ID, email=DEFAULT_EMAIL, name=DEFAULT_NAME, hours=1):
    """Helper function to create JWT tokens"""
    with app.app_context():
        token = jwt.encode(
            {
                "user_id": user_id,
                "email": email,
                "name": name,
                "exp": datetime.now(timezone.utc) + timedelta(hours=hours),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


def create_test_note(
    video_id,
    text="Test note",
    timestamp="1:00",
    user_id=DEFAULT_USER_ID,
    generated_by_ai=False,
):
    """Helper function to create test notes"""
    from vidwiz.shared.models import Note

    return Note(
        video_id=video_id,
        text=text,
        timestamp=timestamp,
        user_id=user_id,
        generated_by_ai=generated_by_ai,
    )


def create_test_user_with_context(app, email="testuser@example.com", name="Test User", password="testpass"):
    """Helper function to create a user within app context"""
    with app.app_context():
        user = User(email=email, name=name, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return user


def create_test_video_with_context(
    app, video_id="test_video", title="Test Video", transcript_available=True
):
    """Helper function to create a video within app context"""
    with app.app_context():
        video = Video(
            video_id=video_id, title=title, transcript_available=transcript_available
        )
        db.session.add(video)
        db.session.commit()
        return video
