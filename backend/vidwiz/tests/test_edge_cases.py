
import pytest
from unittest.mock import patch, MagicMock
import os
from flask import Flask
from pydantic import ValidationError

from vidwiz.app import verify_database_connection, main
from vidwiz.shared.utils import (
    admin_required,
    jwt_or_admin_required,
    jwt_or_lt_token_required,
    store_transcript_in_s3,
    push_note_to_sqs,
)
from vidwiz.shared.schemas import (
    NoteCreate,
    TranscriptResult,
    UserCreate,
)


class TestAppCoverage:
    @patch("vidwiz.app.db")
    @patch("vidwiz.app.logger")
    def test_verify_database_connection_failure(self, mock_logger, mock_db):
        """Test that verify_database_connection exits on database failure."""
        # Setup mock to raise exception
        mock_db.session.execute.side_effect = Exception("DB Connection Failed")
        
        app = Flask(__name__)
        
        # Verify that sys.exit(1) is called
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            verify_database_connection(app)
        
        assert pytest_wrapped_e.type is SystemExit
        assert pytest_wrapped_e.value.code == 1
        mock_logger.exception.assert_called_once()

    @patch("vidwiz.app.create_app")
    @patch("vidwiz.app.verify_database_connection")
    @patch("vidwiz.app.logger")
    def test_main_execution(self, mock_logger, mock_verify_db, mock_create_app):
        """Test the main entry point execution."""
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        
        main()
        
        mock_create_app.assert_called_once()
        mock_verify_db.assert_called_once_with(mock_app)
        mock_logger.info.assert_called_once()
        mock_app.run.assert_called_once_with(debug=True, host="0.0.0.0")


class TestUtilsCoverage:
    def test_admin_required_missing_config(self, app):
        """Test admin_required decorator when ADMIN_TOKEN is not configured."""
        
        @admin_required
        def protected_route():
            return "success"

        with app.test_request_context():
            # Set header but patch env var to be None
            headers = {"Authorization": "Bearer some_token"}
            with patch.dict(os.environ, {}, clear=True):
                # Ensure ADMIN_TOKEN is NOT in env
                if "ADMIN_TOKEN" in os.environ:
                    del os.environ["ADMIN_TOKEN"]
                    
                with patch("vidwiz.shared.utils.request") as mock_request:
                    mock_request.headers = headers
                    
                    response = protected_route()
                    
                    # Should return 500 error
                    assert response[1] == 500
                    assert response[0].json == {"error": "Admin access not configured"}

    def test_jwt_or_admin_required_invalid_token(self, app):
        """Test jwt_or_admin_required with a token that is neither admin nor valid JWT."""
        
        @jwt_or_admin_required
        def protected_route():
            return "success"

        with app.test_request_context():
            headers = {"Authorization": "Bearer invalid_token"}
            
            # Patch env to have an admin token that DOESN'T match our invalid_token
            with patch.dict(os.environ, {"ADMIN_TOKEN": "real_admin_token"}):
                with patch("vidwiz.shared.utils.request") as mock_request:
                    mock_request.headers = headers
                    
                    # Mock jwt.decode to raise Exception
                    with patch("jwt.decode", side_effect=Exception("Invalid JWT")):
                         response = protected_route()
                         
                         # Should return 401 error
                         assert response[1] == 401
                         assert response[0].json == {"error": "Invalid or expired token"}

    def test_store_transcript_in_s3_empty_transcript(self):
        """Test store_transcript_in_s3 returns None when transcript is empty."""
        with patch("vidwiz.shared.utils.S3_BUCKET_NAME", "my-bucket"):
            result = store_transcript_in_s3("video123", None)
            assert result is None
            
            result = store_transcript_in_s3("video123", {})
            assert result is None

    @patch("vidwiz.shared.utils.boto3.client")
    @patch("vidwiz.shared.utils.logger")
    def test_store_transcript_in_s3_exception(self, mock_logger, mock_boto, app):
        """Test store_transcript_in_s3 handles exceptions gracefully."""
        
        # Configure app context for config access
        with app.app_context():
            app.config["AWS_ACCESS_KEY_ID"] = "test"
            app.config["AWS_SECRET_ACCESS_KEY"] = "test" 
            app.config["AWS_REGION"] = "us-east-1"
            
            # Setup mock to raise exception
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3
            mock_s3.put_object.side_effect = Exception("S3 Upload Failed")
            
            # Patch the module-level S3_BUCKET_NAME variable
            with patch("vidwiz.shared.utils.S3_BUCKET_NAME", "test-bucket"):
                result = store_transcript_in_s3("video123", {"text": "foo"})
                
                assert result is None
                mock_logger.error.assert_called_once()

    @patch("vidwiz.shared.utils.boto3.client")
    @patch("vidwiz.shared.utils.logger")
    def test_push_note_to_sqs_exception(self, mock_logger, mock_boto, app):
        """Test push_note_to_sqs handles exceptions gracefully."""
        
        with app.app_context():
            app.config["AWS_ACCESS_KEY_ID"] = "test"
            app.config["AWS_SECRET_ACCESS_KEY"] = "test"
            app.config["AWS_REGION"] = "us-east-1"
            app.config["SQS_QUEUE_URL"] = "http://sqs.url"
            
            # Setup mock to raise exception
            mock_sqs = MagicMock()
            mock_boto.return_value = mock_sqs
            mock_sqs.send_message.side_effect = Exception("SQS Send Failed")
            
            result = push_note_to_sqs({"note": "data"})
            
            assert result is None
            mock_logger.error.assert_called_once()


class TestSchemaValidation:
    def test_note_create_invalid_timestamp_no_colon(self):
        """Test NoteCreate validator rejects timestamps without colon."""
        with pytest.raises(ValidationError) as exc_info:
            NoteCreate(
                video_id="test123",
                timestamp="123",  # No colon
                text="Test note"
            )
        assert "timestamp must contain at least one ':'" in str(exc_info.value)

    def test_note_create_invalid_timestamp_no_numbers(self):
        """Test NoteCreate validator rejects timestamps without enough numbers."""
        with pytest.raises(ValidationError) as exc_info:
            NoteCreate(
                video_id="test123",
                timestamp="a:b",  # Not enough numbers
                text="Test note"
            )
        assert "timestamp must contain at least two numbers" in str(exc_info.value)

    def test_transcript_result_invalid_item_not_dict(self):
        """Test TranscriptResult validator rejects non-dict items."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptResult(
                task_id=1,
                video_id="test123",
                success=True,
                transcript=["not a dict"]  # List item is not a dict
            )
        # Note: This will be caught by pydantic's type checking, not our custom validator
        assert "validation error" in str(exc_info.value).lower()

    def test_transcript_result_invalid_missing_text(self):
        """Test TranscriptResult validator rejects items missing 'text' field."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptResult(
                task_id=1,
                video_id="test123",
                success=True,
                transcript=[{"timestamp": "0:10"}]  # Missing 'text'
            )
        assert "transcript items must contain 'text' field" in str(exc_info.value)

    def test_user_create_empty_email(self):
        """Test UserCreate validator rejects empty email."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="", password="password123", name="Test User")
        assert "Email cannot be empty" in str(exc_info.value)

    def test_user_create_invalid_email(self):
        """Test UserCreate validator rejects invalid email format."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="notanemail", password="password123", name="Test User")
        assert "Invalid email format" in str(exc_info.value)

    def test_user_create_empty_password(self):
        """Test UserCreate validator rejects empty password."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="test@example.com", password="", name="Test User")
        assert "Password cannot be empty" in str(exc_info.value)

    def test_user_create_short_password(self):
        """Test UserCreate validator rejects password with 6 or fewer chars."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="test@example.com", password="123456", name="Test User")
        assert "Password must be more than 6 characters long" in str(exc_info.value)

    def test_user_create_empty_name(self):
        """Test UserCreate validator rejects empty name."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="test@example.com", password="password123", name="")
        assert "Name cannot be empty" in str(exc_info.value)

    def test_user_create_short_name(self):
        """Test UserCreate validator rejects name with fewer than 2 chars."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="test@example.com", password="password123", name="A")
        assert "Name must be at least 2 characters long" in str(exc_info.value)


class TestUtilsAdditionalCoverage:
    def test_jwt_or_lt_token_db_error(self, app):
        """Test jwt_or_lt_token_required when database lookup raises exception."""
        
        @jwt_or_lt_token_required
        def protected_route():
            return "success"

        with app.test_request_context():
            headers = {"Authorization": "Bearer invalid_jwt_token"}
            
            with patch("vidwiz.shared.utils.request") as mock_request:
                mock_request.headers = headers
                
                # Mock jwt.decode to fail (not a valid JWT)
                with patch("jwt.decode", side_effect=Exception("Invalid JWT")):
                    # Mock User.query to raise an exception during long-term token lookup
                    with patch("vidwiz.shared.models.User") as mock_user_class:
                        mock_query = MagicMock()
                        mock_query.filter_by.return_value.first.side_effect = Exception("DB Error")
                        mock_user_class.query = mock_query
                        
                        response = protected_route()
                        
                        # Should return 401 error
                        assert response[1] == 401
                        assert response[0].json == {"error": "Invalid or expired token or not a long term token"}

    def test_admin_required_missing_header(self, app):
        """Test admin_required when Authorization header is missing."""
        
        @admin_required
        def admin_route():
            return "success"

        with app.test_request_context():
            headers = {}  # No Authorization header
            
            with patch("vidwiz.shared.utils.request") as mock_request:
                mock_request.headers = headers
                
                response = admin_route()
                
                # Should return 401 error
                assert response[1] == 401
                assert response[0].json == {"error": "Missing or invalid Authorization header"}
