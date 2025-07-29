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
            with pytest.raises(ValueError, match="DB_URL must be set"):
                create_app()

    def test_create_app_without_test_config_missing_lambda_url(self):
        """Test creating app with AI_NOTE_TOGGLE enabled but missing LAMBDA_URL"""
        with patch.dict(
            os.environ,
            {
                "DB_URL": "postgresql://test:test@localhost/test",
                "AI_NOTE_TOGGLE": "true",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="LAMBDA_URL must be set"):
                create_app()

    def test_create_app_with_production_config(self):
        """Test creating app with production-like configuration"""
        with patch.dict(
            os.environ,
            {
                "DB_URL": "postgresql://test:test@localhost/test",
                "SECRET_KEY": "production_secret",
                "LAMBDA_URL": "https://lambda.aws.com/function",
                "AI_NOTE_TOGGLE": "true",
            },
            clear=True,
        ):
            app = create_app()

            assert (
                app.config["SQLALCHEMY_DATABASE_URI"]
                == "postgresql://test:test@localhost/test"
            )
            assert app.config["SECRET_KEY"] == "production_secret"
            assert app.config["LAMBDA_URL"] == "https://lambda.aws.com/function"
            assert app.config["AI_NOTE_TOGGLE"] is True

    def test_create_app_ai_toggle_disabled(self):
        """Test creating app with AI_NOTE_TOGGLE disabled"""
        with patch.dict(
            os.environ,
            {
                "DB_URL": "postgresql://test:test@localhost/test",
                "AI_NOTE_TOGGLE": "false",
            },
            clear=True,
        ):
            app = create_app()

            assert app.config["AI_NOTE_TOGGLE"] is False
            # LAMBDA_URL is not required when AI_NOTE_TOGGLE is false

    def test_create_app_default_ai_toggle(self):
        """Test creating app with default AI_NOTE_TOGGLE (should be false)"""
        with patch.dict(
            os.environ, {"DB_URL": "postgresql://test:test@localhost/test"}, clear=True
        ):
            app = create_app()

            assert app.config["AI_NOTE_TOGGLE"] is False

    def test_create_app_default_secret_key(self):
        """Test creating app with default secret key when not provided"""
        with patch.dict(
            os.environ, {"DB_URL": "postgresql://test:test@localhost/test"}, clear=True
        ):
            app = create_app()

            assert app.config["SECRET_KEY"] == "dev_secret_key"

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
                "AI_NOTE_TOGGLE": "true",
            },
            clear=True,
        ):
            test_config = {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SECRET_KEY": "test_secret",
                "AI_NOTE_TOGGLE": False,
            }
            app = create_app(test_config)

            # Test config should override environment variables
            assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
            assert app.config["SECRET_KEY"] == "test_secret"
            assert app.config["AI_NOTE_TOGGLE"] is False

    def test_create_app_ai_toggle_case_insensitive(self):
        """Test that AI_NOTE_TOGGLE is case insensitive"""
        test_cases = [
            ("TRUE", True, True),  # Need LAMBDA_URL
            ("True", True, True),  # Need LAMBDA_URL
            ("true", True, True),  # Need LAMBDA_URL
            ("FALSE", False, False),  # Don't need LAMBDA_URL
            ("False", False, False),  # Don't need LAMBDA_URL
            ("false", False, False),  # Don't need LAMBDA_URL
            ("", False, False),  # Default case, don't need LAMBDA_URL
            ("invalid", False, False),  # Invalid value defaults to false
        ]

        for toggle_value, expected, needs_lambda in test_cases:
            env_vars = {
                "DB_URL": "postgresql://test:test@localhost/test",
                "AI_NOTE_TOGGLE": toggle_value,
            }
            if needs_lambda:
                env_vars["LAMBDA_URL"] = "https://test-lambda.com/invoke"

            with patch.dict(os.environ, env_vars, clear=True):
                app = create_app()
                assert app.config["AI_NOTE_TOGGLE"] is expected

    def test_create_app_lambda_url_not_required_when_ai_disabled(self):
        """Test that LAMBDA_URL is not required when AI_NOTE_TOGGLE is disabled"""
        ai_toggle_false_values = ["false", "False", "FALSE", ""]

        for toggle_value in ai_toggle_false_values:
            with patch.dict(
                os.environ,
                {
                    "DB_URL": "postgresql://test:test@localhost/test",
                    "AI_NOTE_TOGGLE": toggle_value,
                    # Intentionally not setting LAMBDA_URL
                },
                clear=True,
            ):
                # This should not raise an error
                app = create_app()
                assert app.config["AI_NOTE_TOGGLE"] is False

    def test_create_app_error_messages(self):
        """Test that error messages are descriptive"""
        # Test DB_URL error message
        with patch.dict(os.environ, {}, clear=True):
            try:
                create_app()
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "DB_URL must be set in the environment variables" in str(e)

        # Test LAMBDA_URL error message
        with patch.dict(
            os.environ,
            {
                "DB_URL": "postgresql://test:test@localhost/test",
                "AI_NOTE_TOGGLE": "true",
            },
            clear=True,
        ):
            try:
                create_app()
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert (
                    "LAMBDA_URL must be set in the environment variables when AI_NOTE_TOGGLE is enabled"
                    in str(e)
                )
