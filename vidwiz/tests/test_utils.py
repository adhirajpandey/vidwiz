import jwt
from datetime import datetime, timedelta, timezone
from vidwiz.shared.utils import jwt_required, send_request_to_ainote_lambda

# Test constants
TEST_USER_ID = 1
TEST_USERNAME = "testuser"
INVALID_TOKEN = "invalid_token"
WRONG_SECRET = "wrong_secret"


class TestJWTRequired:
    def test_jwt_required_decorator_valid_token(self, app):
        """Test JWT decorator with valid token"""
        with app.app_context():
            # Create a valid token
            token = jwt.encode(
                {
                    "user_id": TEST_USER_ID,
                    "username": TEST_USERNAME,
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
                assert result["user_id"] == TEST_USER_ID

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
                assert (
                    result[0].get_json()["error"]
                    == "Invalid or expired token or not a long term token"
                )

    def test_jwt_required_decorator_invalid_token(self, app):
        """Test JWT decorator with various invalid token formats"""
        with app.app_context():

            @jwt_required
            def test_route():
                return {"success": True}

            # Test cases for different invalid token scenarios
            invalid_tokens = [
                "Bearer invalid_token",  # Invalid token string
                "Bearer ",  # Empty token
                "Bearer not.a.valid.jwt",  # Malformed JWT
                "Bearer token1 Bearer token2",  # Multiple Bearer tokens
            ]

            for auth_header in invalid_tokens:
                with app.test_request_context(
                    "/test", headers={"Authorization": auth_header}
                ):
                    result = test_route()
                    assert result[1] == 401
                    assert (
                        result[0].get_json()["error"]
                        == "Invalid or expired token or not a long term token"
                    )

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
                assert (
                    result[0].get_json()["error"]
                    == "Invalid or expired token or not a long term token"
                )


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
