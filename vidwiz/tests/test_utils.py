import pytest
import jwt
from datetime import datetime, timedelta, timezone
from vidwiz.app import create_app
from vidwiz.shared.utils import jwt_required, send_request_to_ainote_lambda
from vidwiz.shared.models import db


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
    def test_send_request_basic_functionality(self, app):
        """Test that lambda function can be called without errors"""
        with app.app_context():
            result = send_request_to_ainote_lambda(
                note_id=1,
                video_id="test123",
                video_title="Test Video",
                note_timestamp="00:01:30",
            )

            # Function should return None (fire and forget)
            assert result is None

    def test_send_request_with_different_parameters(self, app):
        """Test lambda function with different parameter values"""
        with app.app_context():
            result = send_request_to_ainote_lambda(
                note_id=999,
                video_id="special_chars_测试",
                video_title="Video with émojis 🎥",
                note_timestamp="02:30:45",
            )

            # Function should return None regardless of parameters
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
