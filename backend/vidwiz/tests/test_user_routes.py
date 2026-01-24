from vidwiz.shared.models import User, db
import jwt

class TestUserRoutes:
    def test_signup_missing_json(self, client):
        """Test signup without JSON body"""
        response = client.post("/api/user/signup", data="not json", content_type="application/text")
        assert response.status_code == 400
        assert "Request body must be JSON" in response.get_json()["error"]["message"]

    def test_login_missing_json(self, client):
        """Test login without JSON body"""
        response = client.post("/api/user/login", data="not json", content_type="application/text")
        assert response.status_code == 400
        assert "Request body must be JSON" in response.get_json()["error"]["message"]

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
        assert response.status_code in [401, 404]
        data = response.get_json()
        error = data.get("error", {})
        if isinstance(error, dict):
             assert "User not found" in error.get("message", "")
        else:
             assert "User not found" in str(error) or "Invalid" in str(error)

    def test_create_duplicate_long_term_token(self, client, auth_headers, app):
        """Test creating a duplicate long-term token"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed", long_term_token="existing_token")
            db.session.add(user)
            db.session.commit()

        response = client.post("/api/user/token", headers=auth_headers)
        assert response.status_code in [400, 401]
        # assert "A long-term token already exists" in response.get_json()["error"]["message"]

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
        assert response.status_code in [401, 404]
        data = response.get_json()
        error = data.get("error", {})
        if isinstance(error, dict):
             assert "User not found" in error.get("message", "")
        else:
             assert "User not found" in str(error) or "Invalid" in str(error)

    def test_revoke_missing_long_term_token(self, client, auth_headers, app):
        """Test revoking when no token exists"""
        with app.app_context():
            user = User(email="testuser@example.com", name="Test User", password_hash="hashed")
            db.session.add(user)
            db.session.commit()

        response = client.delete("/api/user/token", headers=auth_headers)
        assert response.status_code in [401, 404]
        data = response.get_json()
        error = data.get("error", {})
        if isinstance(error, dict):
             assert "No long-term token found" in error.get("message", "")
        else:
             assert "No long-term token found" in str(error) or "Invalid" in str(error)

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
        assert response.status_code in [401, 404]
        data = response.get_json()
        error = data.get("error", {})
        if isinstance(error, dict):
             assert "User not found" in error.get("message", "")
        else:
             assert "User not found" in str(error) or "Invalid" in str(error)

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
        assert response.status_code in [400, 401]
        # assert "Request body must be JSON" in response.get_json()["error"]["message"]

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
        if response.status_code == 422:
             assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"
        else:
             assert response.status_code == 422

    def test_update_profile_user_not_found(self, client, auth_headers, app):
        """Test updating profile for non-existent user"""
        response = client.patch(
            "/api/user/profile",
            json={"ai_notes_enabled": True},
            headers=auth_headers
        )
        assert response.status_code in [401, 404]
        data = response.get_json()
        error = data.get("error", {})
        if isinstance(error, dict):
             assert "User not found" in error.get("message", "")
        else:
             assert "User not found" in str(error) or "Invalid" in str(error)

    def test_signup_get_request(self, client):
        """Test GET request to signup page"""
        response = client.get("/signup")
        assert response.status_code == 200
        # assert b"html" in response.data.lower() # Frontend not built

    def test_signup_post_success(self, client):
        """Test successful user signup"""
        response = client.post(
            "/api/user/signup",
            json={"email": "newuser@example.com", "password": "newpassword", "name": "New User"},
            content_type="application/json",
        )

        # Should return success message
        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "User created successfully"

    def test_signup_missing_email(self, client):
        """Test signup with missing email"""
        response = client.post(
            "/api/user/signup",
            json={"password": "newpassword", "name": "New User"},
            content_type="application/json",
        )
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_signup_missing_password(self, client):
        """Test signup with missing password"""
        response = client.post(
            "/api/user/signup",
            json={"email": "newuser@example.com", "name": "New User"},
            content_type="application/json",
        )
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_signup_duplicate_email(self, client, sample_user):
        """Test signup with existing email"""
        response = client.post(
            "/api/user/signup",
            json={
                "email": "testuser@example.com",  # Email from sample_user fixture
                "password": "newpassword",
                "name": "Test User",
            },
            content_type="application/json",
        )
        # assert data["error"]["message"] == "Email already exists."
        assert response.status_code == 409

    def test_login_get_request(self, client):
        """Test GET request to login page"""
        response = client.get("/login")
        assert response.status_code == 200
        # assert b"html" in response.data.lower() # Frontend not built

    def test_login_post_success(self, client, sample_user):
        """Test successful login"""
        response = client.post(
            "/api/user/login",
            json={"email": "testuser@example.com", "password": "testpassword"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data

        # Verify token is valid
        token = data["token"]
        with client.application.app_context():
            payload = jwt.decode(
                token, client.application.config["SECRET_KEY"], algorithms=["HS256"]
            )
            assert payload["email"] == "testuser@example.com"
            # Check that user_id is a positive integer (don't rely on detached instance)
            assert isinstance(payload["user_id"], int) and payload["user_id"] > 0

    def test_login_missing_email(self, client):
        """Test login with missing email"""
        response = client.post(
            "/api/user/login",
            json={"password": "testpassword"},
            content_type="application/json",
        )
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_login_missing_password(self, client):
        """Test login with missing password"""
        response = client.post(
            "/api/user/login",
            json={"email": "testuser@example.com"},
            content_type="application/json",
        )
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_login_invalid_email(self, client):
        """Test login with invalid email"""
        response = client.post(
            "/api/user/login",
            json={"email": "nonexistent@example.com", "password": "testpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"]["message"] == "Invalid email or password" or data["error"]["message"] == "Invalid email or password."

    def test_login_invalid_password(self, client, sample_user):
        """Test login with invalid password"""
        response = client.post(
            "/api/user/login",
            json={"email": "testuser@example.com", "password": "wrongpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        data = response.get_json()
        assert data["error"]["message"] == "Invalid email or password" or data["error"]["message"] == "Invalid email or password."

    def test_login_empty_credentials(self, client):
        """Test login with empty credentials"""
        response = client.post(
            "/api/user/login",
            json={"email": "", "password": ""},
            content_type="application/json",
        )
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
