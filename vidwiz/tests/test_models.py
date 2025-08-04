import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
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


class TestUserModel:
    def test_user_creation(self, app):
        """Test basic user creation"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            assert user.id is not None
            assert user.username == "testuser"
            assert user.password_hash == "hashed_password"
            assert user.created_at is not None
            assert isinstance(user.created_at, datetime)

    def test_user_unique_username(self, app):
        """Test that usernames must be unique"""
        with app.app_context():
            user1 = User(username="testuser", password_hash="hash1")
            user2 = User(username="testuser", password_hash="hash2")

            db.session.add(user1)
            db.session.commit()

            db.session.add(user2)
            with pytest.raises(IntegrityError):
                db.session.commit()

    def test_user_relationships(self, app):
        """Test user relationships with videos and notes"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            # Test videos relationship
            video = Video(video_id="vid123", title="Test Video", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            assert len(user.videos) == 1
            assert user.videos[0].title == "Test Video"

            # Test notes relationship
            note = Note(
                video_id="vid123", timestamp="1:23", text="Test note", user_id=user.id
            )
            db.session.add(note)
            db.session.commit()

            assert len(user.notes) == 1
            assert user.notes[0].text == "Test note"


class TestVideoModel:
    def test_video_creation(self, app):
        """Test basic video creation"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video = Video(
                video_id="vid123",
                title="Test Video",
                transcript_available=True,
                user_id=user.id,
            )
            db.session.add(video)
            db.session.commit()

            assert video.id is not None
            assert video.video_id == "vid123"
            assert video.title == "Test Video"
            assert video.transcript_available is True
            assert video.user_id == user.id
            assert video.created_at is not None
            assert video.updated_at is not None

    def test_video_unique_video_id(self, app):
        """Test that video_id must be unique"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video1 = Video(video_id="vid123", title="Video 1", user_id=user.id)
            video2 = Video(video_id="vid123", title="Video 2", user_id=user.id)

            db.session.add(video1)
            db.session.commit()

            db.session.add(video2)
            with pytest.raises(IntegrityError):
                db.session.commit()

    def test_video_defaults(self, app):
        """Test video default values"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid123", title="Test Video", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            assert video.transcript_available is False  # Default value

    def test_video_relationships(self, app):
        """Test video relationships with user and notes"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid123", title="Test Video", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            # Test user relationship
            assert video.user.username == "testuser"

            # Test notes relationship
            note1 = Note(
                video_id="vid123", timestamp="1:23", text="Note 1", user_id=user.id
            )
            note2 = Note(
                video_id="vid123", timestamp="2:45", text="Note 2", user_id=user.id
            )
            db.session.add_all([note1, note2])
            db.session.commit()

            assert len(video.notes) == 2
            assert {note.text for note in video.notes} == {"Note 1", "Note 2"}


class TestNoteModel:
    def test_note_creation(self, app):
        """Test basic note creation"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid123", title="Test Video", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid123",
                timestamp="1:23",
                text="This is a test note",
                generated_by_ai=True,
                user_id=user.id,
            )
            db.session.add(note)
            db.session.commit()

            assert note.id is not None
            assert note.video_id == "vid123"
            assert note.timestamp == "1:23"
            assert note.text == "This is a test note"
            assert note.generated_by_ai is True
            assert note.user_id == user.id
            assert note.created_at is not None
            assert note.updated_at is not None

    def test_note_defaults(self, app):
        """Test note default values"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid123", title="Test Video", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid123", timestamp="1:23", text="Test note", user_id=user.id
            )
            db.session.add(note)
            db.session.commit()

            assert note.generated_by_ai is False  # Default value

    def test_note_relationships(self, app):
        """Test note relationships with user and video"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid123", title="Test Video", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid123", timestamp="1:23", text="Test note", user_id=user.id
            )
            db.session.add(note)
            db.session.commit()

            # Test user relationship
            assert note.user.username == "testuser"

            # Test video relationship
            assert note.video.title == "Test Video"

    def test_cascade_delete(self, app):
        """Test cascade delete behavior"""
        with app.app_context():
            user = User(username="testuser", password_hash="hashed_password")
            db.session.add(user)
            db.session.commit()

            video = Video(video_id="vid123", title="Test Video", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid123", timestamp="1:23", text="Test note", user_id=user.id
            )
            db.session.add(note)
            db.session.commit()
            note_id = note.id

            # Delete video should cascade delete notes
            db.session.delete(video)
            db.session.commit()

            assert db.session.get(Note, note_id) is None

            # Re-create for user deletion test
            video = Video(video_id="vid456", title="Test Video 2", user_id=user.id)
            db.session.add(video)
            db.session.commit()

            note = Note(
                video_id="vid456", timestamp="1:23", text="Test note 2", user_id=user.id
            )
            db.session.add(note)
            db.session.commit()
            note_id = note.id
            video_id = video.id

            # Delete user should cascade delete videos and notes
            db.session.delete(user)
            db.session.commit()

            assert db.session.get(Note, note_id) is None
            assert db.session.get(Video, video_id) is None
