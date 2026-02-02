import pytest
import os
from unittest.mock import patch
from vidwiz.app import create_app


class TestAppCreation:
    """Test application creation and configuration"""

    def test_create_app_with_test_config(self):
        """Test creating app with test configuration"""
        test_config = {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test_secret",
        }
        app = create_app(test_config)

        assert app.config["TESTING"] is True
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
        assert app.config["SECRET_KEY"] == "test_secret"

    def test_create_app_without_test_config_missing_db_url(self):
        """Test creating app without test config and missing DB_URL"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as excinfo:
                create_app()
            assert "Missing required environment variables" in str(excinfo.value)
            assert "DB_URL" in str(excinfo.value)

    def test_create_app_with_production_config(self):
        """Test creating app with production-like configuration"""
        required_env = {
            "DB_URL": "postgresql://test:test@localhost/test",
            "SECRET_KEY": "production_secret",
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_REGION": "us-test-1",
            "SQS_QUEUE_URL": "http://localhost/mock-sqs",
            "S3_BUCKET_NAME": "test-bucket",
            "ADMIN_TOKEN": "admin-token",
            "GEMINI_API_KEY": "test-gemini-key",
            "SQS_AI_NOTE_QUEUE_URL": "test-ai-queue-url",
            "SQS_SUMMARY_QUEUE_URL": "test-summary-queue-url",
        }
        with patch.dict(os.environ, required_env, clear=True):
            app = create_app()
            assert (
                app.config["SQLALCHEMY_DATABASE_URI"]
                == "postgresql://test:test@localhost/test"
            )
            assert app.config["SECRET_KEY"] == "production_secret"

    def test_create_app_default_secret_key(self):
        """Test that app fails if SECRET_KEY is not set in environment"""
        required_env = {
            "DB_URL": "postgresql://test:test@localhost/test",
            # SECRET_KEY intentionally omitted to test strict requirement
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_REGION": "us-test-1",
            "SQS_QUEUE_URL": "http://localhost/mock-sqs",
            "S3_BUCKET_NAME": "test-bucket",
            "ADMIN_TOKEN": "admin-token",
            "GEMINI_API_KEY": "test-gemini-key",
            "SQS_AI_NOTE_QUEUE_URL": "test-ai-queue-url",
            "SQS_SUMMARY_QUEUE_URL": "test-summary-queue-url",
        }
        with patch.dict(os.environ, required_env, clear=True):
            with pytest.raises(ValueError) as excinfo:
                create_app()
            assert "Missing required environment variables" in str(excinfo.value)
            assert "SECRET_KEY" in str(excinfo.value)

    def test_create_app_blueprints_registered(self):
        """Test that all blueprints are properly registered"""
        test_config = {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test_secret",
        }
        app = create_app(test_config)

        # Check that blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        expected_blueprints = ["core", "video", "notes"]

        for expected_bp in expected_blueprints:
            assert expected_bp in blueprint_names

    def test_create_app_database_initialization(self):
        """Test that database is properly initialized"""
        test_config = {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test_secret",
        }
        app = create_app(test_config)

        # Test that database is initialized
        from vidwiz.shared.models import db

        with app.app_context():
            # This should not raise an error if database is properly initialized
            db.create_all()

            # Test that tables can be queried (which means they exist)
            from vidwiz.shared.models import User, Video, Note

            # Try to query each table - this will fail if tables don't exist
            try:
                User.query.count()
                Video.query.count()
                Note.query.count()
                # If we get here, tables exist
                assert True
            except Exception as e:
                assert False, f"Database tables not properly created: {e}"

    def test_create_app_configuration_precedence(self):
        """Test that test_config takes precedence over environment variables"""
        with patch.dict(
            os.environ,
            {
                "DB_URL": "postgresql://env:env@localhost/env",
                "SECRET_KEY": "env_secret",
            },
            clear=True,
        ):
            test_config = {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SECRET_KEY": "test_secret",
            }
            app = create_app(test_config)

            # Test config should override environment variables
            assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
            assert app.config["SECRET_KEY"] == "test_secret"

    def test_create_app_error_messages(self):
        """Test that error messages are descriptive"""
        # Test DB_URL error message
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as excinfo:
                create_app()
            assert "Missing required environment variables" in str(excinfo.value)
            assert "DB_URL" in str(excinfo.value)
