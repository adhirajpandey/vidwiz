import pytest
from vidwiz.shared.models import User, db

class TestUserRoutes:
    def test_signup_missing_json(self, client):
        """Test signup without JSON body"""
        response = client.post("/api/user/signup", data="not json", content_type="application/text")
        assert response.status_code == 400
        assert "Request body must be JSON" in response.get_json()["error"]

    def test_login_missing_json(self, client):
        """Test login without JSON body"""
        response = client.post("/api/user/login", data="not json", content_type="application/text")
        assert response.status_code == 400
        assert "Request body must be JSON" in response.get_json()["error"]

    def test_create_long_term_token(self, client, auth_headers, app):
        """Test creating a long-term token"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

        response = client.post("/api/user/token", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["message"] == "Long-term token generated successfully"

        # Verify token in DB
        with app.app_context():
            user = User.query.filter_by(email="testuser@example.com").first()
            assert user.long_term_token == data["token"]

    def test_create_long_term_token_user_not_found(self, client, auth_headers, app):
        """Test creating a long-term token for non-existent user"""
        # We don't create the user in the DB, so the token user_id won't match anyone
        response = client.post("/api/user/token", headers=auth_headers)
        assert response.status_code == 404
        assert "User not found" in response.get_json()["error"]

    def test_create_duplicate_long_term_token(self, client, auth_headers, app):
        """Test creating a duplicate long-term token"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed", long_term_token="existing_token")
            db.session.add(user)
            db.session.commit()

        response = client.post("/api/user/token", headers=auth_headers)
        assert response.status_code == 400
        assert "A long-term token already exists" in response.get_json()["error"]

    def test_revoke_long_term_token(self, client, auth_headers, app):
        """Test revoking a long-term token"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed", long_term_token="existing_token")
            db.session.add(user)
            db.session.commit()

        response = client.delete("/api/user/token", headers=auth_headers)
        assert response.status_code == 200
        assert "Long-term token revoked successfully" in response.get_json()["message"]

        # Verify token removed from DB
        with app.app_context():
            user = User.query.filter_by(email="testuser@example.com").first()
            assert user.long_term_token is None

    def test_revoke_long_term_token_user_not_found(self, client, auth_headers, app):
        """Test revoking token for non-existent user"""
        response = client.delete("/api/user/token", headers=auth_headers)
        assert response.status_code == 404
        assert "User not found" in response.get_json()["error"]

    def test_revoke_missing_long_term_token(self, client, auth_headers, app):
        """Test revoking when no token exists"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

        response = client.delete("/api/user/token", headers=auth_headers)
        assert response.status_code == 404
        assert "No long-term token found" in response.get_json()["error"]

    def test_get_profile(self, client, auth_headers, app):
        """Test getting user profile"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed", profile_data={"ai_notes_enabled": True})
            db.session.add(user)
            db.session.commit()

        response = client.get("/api/user/profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["email"] == "testuser@example.com"
        assert data["name"] == "Test User"
        assert data["ai_notes_enabled"] is True
        assert data["token_exists"] is False

    def test_get_profile_user_not_found(self, client, auth_headers, app):
        """Test getting profile for non-existent user"""
        response = client.get("/api/user/profile", headers=auth_headers)
        assert response.status_code == 404
        assert "User not found" in response.get_json()["error"]

    def test_update_profile(self, client, auth_headers, app):
        """Test updating user profile"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

        response = client.patch(
            "/api/user/profile",
            json={"ai_notes_enabled": True},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ai_notes_enabled"] is True

        # Verify DB update
        with app.app_context():
            user = User.query.filter_by(email="testuser@example.com").first()
            assert user.profile_data["ai_notes_enabled"] is True

    def test_update_profile_missing_json(self, client, auth_headers):
        """Test updating profile without JSON body"""
        response = client.patch("/api/user/profile", data="not json", headers=auth_headers, content_type="application/text")
        assert response.status_code == 400
        assert "Request body must be JSON" in response.get_json()["error"]

    def test_update_profile_validation_error(self, client, auth_headers, app):
        """Test updating profile with invalid data"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

        response = client.patch(
            "/api/user/profile",
            json={"ai_notes_enabled": "not boolean"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Invalid" in response.get_json()["error"]

    def test_update_profile_user_not_found(self, client, auth_headers, app):
        """Test updating profile for non-existent user"""
        response = client.patch(
            "/api/user/profile",
            json={"ai_notes_enabled": True},
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "User not found" in response.get_json()["error"]
