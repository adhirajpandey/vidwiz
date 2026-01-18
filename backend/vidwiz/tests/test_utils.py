import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, jsonify
from vidwiz.shared.utils import (
    jwt_or_lt_token_required,
    admin_required,
    jwt_or_admin_required,
    store_transcript_in_s3,
    push_note_to_sqs,
    check_required_env_vars
)
from vidwiz.shared.models import User, db
import jwt
import os

class TestUtils:
    """Test shared utilities"""

    @pytest.fixture
    def mock_app(self):
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test_secret"
        app.config["AWS_ACCESS_KEY_ID"] = "test_access"
        app.config["AWS_SECRET_ACCESS_KEY"] = "test_secret_key"
        app.config["AWS_REGION"] = "test-region"
        app.config["SQS_QUEUE_URL"] = "http://sqs-url"
        return app

    def test_jwt_or_lt_token_required_valid_jwt(self, mock_app):
        # We need to manually set the headers in the request context correctly
        token = jwt.encode({"user_id": 1}, "test_secret", algorithm="HS256")

        with mock_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            @jwt_or_lt_token_required
            def protected_route():
                return "success"

            assert protected_route() == "success"

    def test_jwt_or_lt_token_required_valid_lt_token(self, mock_app):
        # We need an app context to mock database queries
        with mock_app.app_context():
            # Mock User query
            mock_user = MagicMock()
            mock_user.id = 1

            with patch("vidwiz.shared.models.User.query") as mock_query:
                mock_query.filter_by.return_value.first.return_value = mock_user

                with mock_app.test_request_context(headers={"Authorization": "Bearer lt_token_123"}):
                    @jwt_or_lt_token_required
                    def protected_route():
                        return "success"

                    assert protected_route() == "success"

    def test_jwt_or_lt_token_required_invalid_token(self, mock_app):
        with mock_app.app_context():
            # Mock User query to return None for LT token check
            with patch("vidwiz.shared.models.User.query") as mock_query:
                mock_query.filter_by.return_value.first.return_value = None

                with mock_app.test_request_context(headers={"Authorization": "Bearer invalid_token"}):
                    @jwt_or_lt_token_required
                    def protected_route():
                        return "success"

                    response = protected_route()
                    assert response[1] == 401

    def test_admin_required_success(self, mock_app):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "admin_token"}):
            with mock_app.test_request_context(headers={"Authorization": "Bearer admin_token"}):
                @admin_required
                def admin_route():
                    return "success"

                assert admin_route() == "success"

    def test_admin_required_failure(self, mock_app):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "admin_token"}):
            with mock_app.test_request_context(headers={"Authorization": "Bearer wrong_token"}):
                @admin_required
                def admin_route():
                    return "success"

                response = admin_route()
                assert response[1] == 403

    def test_jwt_or_admin_required_admin_success(self, mock_app):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "admin_token"}):
            with mock_app.test_request_context(headers={"Authorization": "Bearer admin_token"}):
                @jwt_or_admin_required
                def shared_route():
                    return "success"

                assert shared_route() == "success"

    def test_jwt_or_admin_required_jwt_success(self, mock_app):
        token = jwt.encode({"user_id": 1}, "test_secret", algorithm="HS256")
        with mock_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            @jwt_or_admin_required
            def shared_route():
                return "success"

            assert shared_route() == "success"

    def test_store_transcript_in_s3_success(self, mock_app):
        with patch("boto3.client") as mock_boto:
            with patch("vidwiz.shared.utils.S3_BUCKET_NAME", "test_bucket"):
                with mock_app.app_context():
                    store_transcript_in_s3("vid1", [{"text": "hello"}])
                    mock_boto.return_value.put_object.assert_called()

    def test_store_transcript_in_s3_missing_bucket(self, mock_app):
        with patch("vidwiz.shared.utils.S3_BUCKET_NAME", None):
             with mock_app.app_context():
                result = store_transcript_in_s3("vid1", [{"text": "hello"}])
                assert result is None

    def test_push_note_to_sqs_success(self, mock_app):
        with patch("boto3.client") as mock_boto:
            mock_boto.return_value.send_message.return_value = {"MessageId": "123"}

            with mock_app.app_context():
                response = push_note_to_sqs({"note_id": 1})
                assert response["MessageId"] == "123"

    def test_check_required_env_vars_success(self):
        env_vars = {
            "DB_URL": "db",
            "SECRET_KEY": "secret",
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_REGION": "region",
            "SQS_QUEUE_URL": "url",
            "S3_BUCKET_NAME": "bucket",
            "ADMIN_TOKEN": "token"
        }
        with patch.dict(os.environ, env_vars):
            check_required_env_vars() # Should not raise

    def test_check_required_env_vars_failure(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                check_required_env_vars()
