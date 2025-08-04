import pytest
from unittest.mock import patch, Mock
import jwt
from datetime import datetime, timedelta, timezone
from vidwiz.app import create_app
from vidwiz.shared.utils import jwt_required, send_request_to_ainote_lambda
from vidwiz.shared.models import db
import requests


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


class TestJWTRequired:
    def test_jwt_required_decorator_valid_token(self, app):
        """Test JWT decorator with valid token"""
        with app.app_context():
            # Create a valid token
            token = jwt.encode(
                {
                    "user_id": 1,
                    "username": "testuser",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )

            @jwt_required
            def test_route():
                from flask import request

                return {"user_id": request.user_id}

            # Mock request with valid token
            with app.test_request_context(
                "/test", headers={"Authorization": f"Bearer {token}"}
            ):
                result = test_route()
                assert result["user_id"] == 1

    def test_jwt_required_decorator_missing_header(self, app):
        """Test JWT decorator with missing Authorization header"""
        with app.app_context():

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request without Authorization header
            with app.test_request_context("/test"):
                result = test_route()
                # The decorator returns a tuple (response, status_code)
                assert result[1] == 401
                assert (
                    result[0].get_json()["error"]
                    == "Missing or invalid Authorization header"
                )
                assert result[1] == 401

    def test_jwt_required_decorator_invalid_header_format(self, app):
        """Test JWT decorator with invalid Authorization header format"""
        with app.app_context():

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request with invalid header format
            with app.test_request_context(
                "/test", headers={"Authorization": "InvalidToken"}
            ):
                result = test_route()
                assert result[1] == 401
                assert (
                    result[0].get_json()["error"]
                    == "Missing or invalid Authorization header"
                )
                assert result[1] == 401

    def test_jwt_required_decorator_expired_token(self, app):
        """Test JWT decorator with expired token"""
        with app.app_context():
            # Create an expired token
            token = jwt.encode(
                {
                    "user_id": 1,
                    "username": "testuser",
                    "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
                },
                app.config["SECRET_KEY"],
                algorithm="HS256",
            )

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request with expired token
            with app.test_request_context(
                "/test", headers={"Authorization": f"Bearer {token}"}
            ):
                result = test_route()
                assert result[1] == 401
                assert result[0].get_json()["error"] == "Invalid or expired token"
                assert result[1] == 401

    def test_jwt_required_decorator_invalid_token(self, app):
        """Test JWT decorator with invalid token"""
        with app.app_context():

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request with invalid token
            with app.test_request_context(
                "/test", headers={"Authorization": "Bearer invalid_token"}
            ):
                result = test_route()
                assert result[1] == 401
                assert result[0].get_json()["error"] == "Invalid or expired token"
                assert result[1] == 401

    def test_jwt_required_decorator_wrong_secret(self, app):
        """Test JWT decorator with token signed with wrong secret"""
        with app.app_context():
            # Create a token with wrong secret
            token = jwt.encode(
                {
                    "user_id": 1,
                    "username": "testuser",
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                "wrong_secret",  # Wrong secret
                algorithm="HS256",
            )

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request with token signed with wrong secret
            with app.test_request_context(
                "/test", headers={"Authorization": f"Bearer {token}"}
            ):
                result = test_route()
                assert result[1] == 401
                assert result[0].get_json()["error"] == "Invalid or expired token"
                assert result[1] == 401


class TestSendRequestToAINoteLambda:
    @patch("vidwiz.shared.utils.requests.post")
    def test_send_request_success(self, mock_post):
        """Test successful request to AI note lambda"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        payload = {"video_id": "test123", "timestamp": "00:01:30"}
        lambda_url = "https://test-lambda.com/invoke"
        auth_token = "test_token"

        result = send_request_to_ainote_lambda(payload, lambda_url, auth_token)

        # Function should return None (it doesn't return response)
        assert result is None

        # Verify the request was made with correct parameters
        mock_post.assert_called_once_with(
            lambda_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            },
        )

    @patch("vidwiz.shared.utils.requests.post")
    def test_send_request_exception(self, mock_post):
        """Test request failure to AI note lambda"""
        mock_post.side_effect = requests.RequestException("Connection error")

        payload = {"video_id": "test123", "timestamp": "00:01:30"}
        lambda_url = "https://test-lambda.com/invoke"
        auth_token = "test_token"

        result = send_request_to_ainote_lambda(payload, lambda_url, auth_token)

        # Function should return None when exception occurs
        assert result is None

        # Verify the request was attempted
        mock_post.assert_called_once()

    @patch("vidwiz.shared.utils.requests.post")
    def test_send_request_different_payloads(self, mock_post):
        """Test sending different payload types"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Test with complex payload
        complex_payload = {
            "video_id": "vid123",
            "timestamp": "00:02:45",
            "user_id": 42,
            "note_text": "Complex note with special chars: !@#$%",
            "metadata": {"source": "test", "priority": "high"},
        }
        lambda_url = "https://test-lambda.com/invoke"
        auth_token = "complex_token_123"

        send_request_to_ainote_lambda(complex_payload, lambda_url, auth_token)

        mock_post.assert_called_once_with(
            lambda_url,
            json=complex_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            },
        )

    @patch("vidwiz.shared.utils.requests.post")
    def test_send_request_empty_payload(self, mock_post):
        """Test sending empty payload"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        payload = {}
        lambda_url = "https://test-lambda.com/invoke"
        auth_token = "test_token"

        send_request_to_ainote_lambda(payload, lambda_url, auth_token)

        mock_post.assert_called_once_with(
            lambda_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            },
        )

    @patch("vidwiz.shared.utils.requests.post")
    def test_send_request_timeout_exception(self, mock_post):
        """Test request timeout to AI note lambda"""
        mock_post.side_effect = requests.Timeout("Request timed out")

        payload = {"video_id": "test123"}
        lambda_url = "https://slow-lambda.com/invoke"
        auth_token = "test_token"

        result = send_request_to_ainote_lambda(payload, lambda_url, auth_token)

        # Function should return None when timeout occurs
        assert result is None

    @patch("vidwiz.shared.utils.requests.post")
    def test_send_request_connection_error(self, mock_post):
        """Test connection error to AI note lambda"""
        mock_post.side_effect = requests.ConnectionError("Failed to connect")

        payload = {"video_id": "test123"}
        lambda_url = "https://unreachable-lambda.com/invoke"
        auth_token = "test_token"

        result = send_request_to_ainote_lambda(payload, lambda_url, auth_token)

        # Function should return None when connection error occurs
        assert result is None

    def test_jwt_required_decorator_multiple_bearer_tokens(self, app):
        """Test JWT decorator with multiple Bearer tokens in header"""
        with app.app_context():

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request with malformed header containing multiple Bearer tokens
            with app.test_request_context(
                "/test", headers={"Authorization": "Bearer token1 Bearer token2"}
            ):
                result = test_route()
                assert result[1] == 401
                assert result[0].get_json()["error"] == "Invalid or expired token"

    def test_jwt_required_decorator_empty_token(self, app):
        """Test JWT decorator with empty token after Bearer"""
        with app.app_context():

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request with empty token
            with app.test_request_context(
                "/test", headers={"Authorization": "Bearer "}
            ):
                result = test_route()
                assert result[1] == 401
                assert result[0].get_json()["error"] == "Invalid or expired token"

    def test_jwt_required_decorator_malformed_jwt(self, app):
        """Test JWT decorator with malformed JWT token"""
        with app.app_context():

            @jwt_required
            def test_route():
                return {"success": True}

            # Mock request with malformed JWT
            with app.test_request_context(
                "/test", headers={"Authorization": "Bearer not.a.valid.jwt"}
            ):
                result = test_route()
                assert result[1] == 401
                assert result[0].get_json()["error"] == "Invalid or expired token"

    def test_send_request_special_characters_in_payload(self):
        """Test send request with special characters in payload"""
        payload = {
            "text": "Test with special chars: áéíóú ñ 中文 🎥",
            "video_id": "vid_123_测试",
        }
        lambda_url = "https://test-lambda.com/invoke"
        auth_token = "test_token"

        with patch("vidwiz.shared.utils.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            send_request_to_ainote_lambda(payload, lambda_url, auth_token)

            # Should handle unicode characters without issues
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["json"] == payload

    def test_send_request_large_payload(self):
        """Test send request with large payload"""
        payload = {
            "text": "x" * 10000,  # Large text payload
            "video_id": "vid_123",
        }
        lambda_url = "https://test-lambda.com/invoke"
        auth_token = "test_token"

        with patch("vidwiz.shared.utils.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            send_request_to_ainote_lambda(payload, lambda_url, auth_token)

            # Should handle large payloads
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert len(kwargs["json"]["text"]) == 10000
