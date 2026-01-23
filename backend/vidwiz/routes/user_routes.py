from flask import Blueprint, jsonify, request
from vidwiz.shared.utils import jwt_or_lt_token_required, require_json_body
from vidwiz.shared.models import User, db
from vidwiz.shared.schemas import (
    UserCreate,
    UserLogin,
    UserProfileRead,
    UserProfileUpdate,
    TokenResponse,
    TokenRevokeResponse,
)
from vidwiz.shared.errors import (
    handle_validation_error,
    NotFoundError,
    BadRequestError,
    UnauthorizedError,
    ConflictError,
)
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app
from pydantic import ValidationError
from vidwiz.shared.logging import get_logger
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

user_bp = Blueprint("user", __name__)
logger = get_logger("vidwiz.routes.user_routes")


@user_bp.route("/user/signup", methods=["POST"])
@require_json_body
def signup():
    try:
        user_data = UserCreate.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Signup validation error: {e}")
        return handle_validation_error(e)

    if User.query.filter_by(email=user_data.email).first():
        logger.info(f"Signup attempt with existing email='{user_data.email}'")
        raise ConflictError("Email already exists")

    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=generate_password_hash(user_data.password),
    )
    db.session.add(user)
    db.session.commit()
    logger.info(
        f"User created successfully email='{user_data.email}', id={user.id}"
    )

    return jsonify({"message": "User created successfully"}), 201


@user_bp.route("/user/login", methods=["POST"])
@require_json_body
def login():
    try:
        login_data = UserLogin.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Login validation error: {e}")
        return handle_validation_error(e)

    user = User.query.filter_by(email=login_data.email).first()
    if not user or not user.password_hash or not check_password_hash(user.password_hash, login_data.password):
        logger.warning(f"Invalid login for email='{login_data.email}'")
        raise UnauthorizedError("Invalid email or password")

    token = jwt.encode(
        {
            "user_id": user.id,
            "email": user.email,
            "name": user.name or user.email,
            "profile_image_url": user.profile_image_url,
            "exp": datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    logger.info(f"Login success email='{login_data.email}', user_id={user.id}")
    return jsonify({"token": token})


@user_bp.route("/user/token", methods=["POST"])
@jwt_or_lt_token_required
def create_long_term_token():
    """Generate a new long-term token"""
    user = User.query.get(request.user_id)
    if not user:
        logger.warning(
            f"Long-term token creation for missing user_id={request.user_id}"
        )
        raise NotFoundError("User not found")

    if user.long_term_token:
        logger.warning(
            f"User_id={user.id} attempted to create duplicate long-term token"
        )
        raise BadRequestError(
            "A long-term token already exists. Please revoke the existing token before generating a new one."
        )

    long_term_token = jwt.encode(
        {
            "user_id": user.id,
            "email": user.email,
            "type": "long_term",  # Add type to distinguish from regular tokens
            "iat": datetime.now(timezone.utc).timestamp(),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    # Store the token in the user's record
    user.long_term_token = long_term_token
    db.session.commit()
    logger.info(f"Long-term token generated for user_id={user.id}")

    # Validate response using schema
    response_data = {
        "message": "Long-term token generated successfully",
        "token": long_term_token,
    }
    validated_response = TokenResponse.model_validate(response_data)
    return jsonify(validated_response.model_dump()), 200


@user_bp.route("/user/token", methods=["DELETE"])
@jwt_or_lt_token_required
def revoke_long_term_token():
    """Revoke the existing long-term token"""
    user = User.query.get(request.user_id)
    if not user:
        logger.warning(
            f"Long-term token revocation for missing user_id={request.user_id}"
        )
        raise NotFoundError("User not found")

    if not user.long_term_token:
        logger.warning(
            f"Token revoke requested but none exists for user_id={user.id}"
        )
        raise NotFoundError("No long-term token found")

    user.long_term_token = None
    db.session.commit()
    logger.info(f"Long-term token revoked for user_id={user.id}")

    response_data = {"message": "Long-term token revoked successfully"}
    validated_response = TokenRevokeResponse.model_validate(response_data)
    return jsonify(validated_response.model_dump()), 200


@user_bp.route("/user/profile", methods=["GET"])
@jwt_or_lt_token_required
def get_profile():
    """Get user profile data"""
    user = User.query.get(request.user_id)
    if not user:
        logger.warning(f"Profile requested for missing user_id={request.user_id}")
        raise NotFoundError("User not found")

    ai_notes_enabled = False
    if user.profile_data and isinstance(user.profile_data, dict):
        ai_notes_enabled = user.profile_data.get("ai_notes_enabled", False)

    token_exists = user.long_term_token is not None

    profile_data = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_image_url": user.profile_image_url,
        "ai_notes_enabled": ai_notes_enabled,
        "token_exists": token_exists,
        "long_term_token": user.long_term_token,
        "created_at": user.created_at,
    }

    validated_profile = UserProfileRead.model_validate(profile_data)
    logger.debug(f"Profile fetched for user_id={user.id}")
    return jsonify(validated_profile.model_dump()), 200


@user_bp.route("/user/profile", methods=["PATCH"])
@jwt_or_lt_token_required
@require_json_body
def update_profile():
    """Update user profile data (name, ai_notes_enabled). Email is immutable."""
    try:
        update_data = UserProfileUpdate.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Update profile validation error: {e}")
        return handle_validation_error(e)

    user = User.query.get(request.user_id)
    if not user:
        logger.warning(f"Update profile for missing user_id={request.user_id}")
        raise NotFoundError("User not found")

    # Update fields if provided
    if update_data.name is not None:
        user.name = update_data.name
    if update_data.ai_notes_enabled is not None:
        if user.profile_data is None:
            user.profile_data = {}
        user.profile_data["ai_notes_enabled"] = update_data.ai_notes_enabled
        flag_modified(user, "profile_data")

    db.session.commit()
    logger.info(f"Updated profile for user_id={user.id}")

    # Return updated profile data
    ai_notes_enabled = False
    if user.profile_data and isinstance(user.profile_data, dict):
        ai_notes_enabled = user.profile_data.get("ai_notes_enabled", False)

    token_exists = user.long_term_token is not None
    profile_data = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_image_url": user.profile_image_url,
        "ai_notes_enabled": ai_notes_enabled,
        "token_exists": token_exists,
        "created_at": user.created_at,
    }

    validated_profile = UserProfileRead.model_validate(profile_data)
    return jsonify(validated_profile.model_dump()), 200


@user_bp.route("/user/google/login", methods=["POST"])
@require_json_body
def google_login():
    """
    Handle Google Sign-In from the frontend.
    Frontend sends Google ID token (credential), backend verifies it and creates/logs in user.
    """
    credential = request.json_data.get("credential")
    if not credential:
        logger.warning("Google login attempt missing credential")
        raise BadRequestError("Missing Google credential")

    google_client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not google_client_id:
        logger.error("GOOGLE_CLIENT_ID not configured")
        # Let global handler catch this as internal error
        raise Exception("Google OAuth not configured")

    try:
        # Verify the Google ID token
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            google_client_id
        )

        # Extract user info from the verified token
        google_id = idinfo["sub"]
        email = idinfo.get("email")
        
        if not email:
            logger.warning("Google login without email - email is required")
            raise BadRequestError("Email is required for Google Sign-In")
        
        name = idinfo.get("name", email.split("@")[0])
        picture = idinfo.get("picture")  # Profile image URL from Google

        logger.info(f"Google login attempt for google_id={google_id}, email={email}")

        # Find existing user by google_id or email
        user = User.query.filter_by(google_id=google_id).first()

        if not user:
            # Check if email already exists (user signed up with password, now linking Google)
            user = User.query.filter_by(email=email).first()
            if user:
                # Link Google account to existing user
                user.google_id = google_id
                logger.info(f"Linked Google account to existing user_id={user.id}")

        if not user:
            # Create new user with email as primary identifier
            user = User(
                email=email,
                google_id=google_id,
                name=name,
                profile_image_url=picture,
            )
            db.session.add(user)
            logger.info(f"Created new Google user with email='{email}'")
        
        # If user exists but name is missing, update it
        if user and not user.name:
            user.name = name
        
        # Always update profile image URL on login (in case it changed)
        if user and picture:
            user.profile_image_url = picture

        db.session.commit()

        # Generate JWT token
        token = jwt.encode(
            {
                "user_id": user.id,
                "email": user.email,
                "name": user.name or user.email,
                "profile_image_url": user.profile_image_url,
                "exp": datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )

        logger.info(f"Google login success for user_id={user.id}, email='{user.email}'")
        return jsonify({"token": token})

    except ValueError as e:
        # Invalid token
        logger.warning(f"Invalid Google token: {e}")
        raise UnauthorizedError("Invalid Google credential")

