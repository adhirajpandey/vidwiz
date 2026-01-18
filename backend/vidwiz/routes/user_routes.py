from flask import Blueprint, jsonify, request
from vidwiz.shared.utils import jwt_or_lt_token_required
from vidwiz.shared.models import User, db
from vidwiz.shared.schemas import (
    UserCreate,
    UserLogin,
    UserProfileRead,
    UserProfileUpdate,
    TokenResponse,
    TokenRevokeResponse,
)
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app
from pydantic import ValidationError
from vidwiz.shared.logging import get_logger

user_bp = Blueprint("user", __name__)
logger = get_logger("vidwiz.routes.user_routes")


@user_bp.route("/user/signup", methods=["POST"])
def signup():
    # Allow silent failure so we can check if data is None and return our custom error
    data = request.get_json(silent=True)
    if not data:
        logger.warning("Signup attempt missing JSON body")
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        user_data = UserCreate(**data)
    except ValidationError as e:
        logger.warning(f"Signup validation error: {e}")
        return jsonify({"error": f"Invalid data: {str(e)}"}), 400

    if User.query.filter_by(username=user_data.username).first():
        logger.info(f"Signup attempt with existing username='{user_data.username}'")
        return jsonify({"error": "Username already exists."}), 400

    user = User(
        username=user_data.username,
        password_hash=generate_password_hash(user_data.password),
    )
    db.session.add(user)
    db.session.commit()
    logger.info(
        f"User created successfully username='{user_data.username}', id={user.id}"
    )

    return jsonify({"message": "User created successfully"}), 201


@user_bp.route("/user/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        logger.warning("Login attempt missing JSON body")
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        login_data = UserLogin(**data)
    except ValidationError as e:
        logger.warning(f"Login validation error: {e}")
        return jsonify({"error": f"Invalid data: {str(e)}"}), 400

    user = User.query.filter_by(username=login_data.username).first()
    if not user or not check_password_hash(user.password_hash, login_data.password):
        logger.warning(f"Invalid login for username='{login_data.username}'")
        return jsonify({"error": "Invalid username or password."}), 401

    token = jwt.encode(
        {
            "user_id": user.id,
            "username": user.username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    logger.info(f"Login success username='{login_data.username}', user_id={user.id}")
    return jsonify({"token": token})


@user_bp.route("/user/token", methods=["POST"])
@jwt_or_lt_token_required
def create_long_term_token():
    """Generate a new long-term token"""
    try:
        user = User.query.get(request.user_id)
        if not user:
            logger.warning(
                f"Long-term token creation for missing user_id={request.user_id}"
            )
            return jsonify({"error": "User not found"}), 404

        if user.long_term_token:
            logger.warning(
                f"User_id={user.id} attempted to create duplicate long-term token"
            )
            return jsonify(
                {
                    "error": "A long-term token already exists. Please revoke the existing token before generating a new one."
                }
            ), 400

        long_term_token = jwt.encode(
            {
                "user_id": user.id,
                "username": user.username,
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
        validated_response = TokenResponse(**response_data)
        return jsonify(validated_response.model_dump()), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error in create_long_term_token: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@user_bp.route("/user/token", methods=["DELETE"])
@jwt_or_lt_token_required
def revoke_long_term_token():
    """Revoke the existing long-term token"""
    try:
        user = User.query.get(request.user_id)
        if not user:
            logger.warning(
                f"Long-term token revocation for missing user_id={request.user_id}"
            )
            return jsonify({"error": "User not found"}), 404

        if not user.long_term_token:
            logger.warning(
                f"Token revoke requested but none exists for user_id={user.id}"
            )
            return jsonify({"error": "No long-term token found"}), 404

        user.long_term_token = None
        db.session.commit()
        logger.info(f"Long-term token revoked for user_id={user.id}")

        response_data = {"message": "Long-term token revoked successfully"}
        validated_response = TokenRevokeResponse(**response_data)
        return jsonify(validated_response.model_dump()), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error in revoke_long_term_token: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@user_bp.route("/user/profile", methods=["GET"])
@jwt_or_lt_token_required
def get_profile():
    """Get user profile data"""
    try:
        user = User.query.get(request.user_id)
        if not user:
            logger.warning(f"Profile requested for missing user_id={request.user_id}")
            return jsonify({"error": "User not found"}), 404

        ai_notes_enabled = False
        if user.profile_data and isinstance(user.profile_data, dict):
            ai_notes_enabled = user.profile_data.get("ai_notes_enabled", False)

        token_exists = user.long_term_token is not None

        profile_data = {
            "id": user.id,
            "username": user.username,
            "ai_notes_enabled": ai_notes_enabled,
            "token_exists": token_exists,
            "long_term_token": user.long_term_token,
        }

        validated_profile = UserProfileRead(**profile_data)
        logger.debug(f"Profile fetched for user_id={user.id}")
        return jsonify(validated_profile.model_dump()), 200

    except Exception as e:
        logger.exception(f"Error in get_profile: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@user_bp.route("/user/profile", methods=["PATCH"])
@jwt_or_lt_token_required
def update_profile():
    """Update user profile data"""
    try:
        data = request.get_json(silent=True)
        if not data:
            logger.warning("Update profile missing JSON body")
            return jsonify({"error": "Request body must be JSON"}), 400

        try:
            update_data = UserProfileUpdate(**data)
        except ValidationError as e:
            logger.warning(f"Update profile validation error: {e}")
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        user = User.query.get(request.user_id)
        if not user:
            logger.warning(f"Update profile for missing user_id={request.user_id}")
            return jsonify({"error": "User not found"}), 404

        if user.profile_data is None:
            user.profile_data = {}

        user.profile_data["ai_notes_enabled"] = update_data.ai_notes_enabled
        flag_modified(user, "profile_data")

        db.session.commit()
        logger.info(
            f"Updated ai_notes_enabled={update_data.ai_notes_enabled} for user_id={user.id}"
        )

        token_exists = user.long_term_token is not None
        profile_data = {
            "id": user.id,
            "username": user.username,
            "ai_notes_enabled": update_data.ai_notes_enabled,
            "token_exists": token_exists,
        }

        validated_profile = UserProfileRead(**profile_data)
        return jsonify(validated_profile.model_dump()), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error in update_profile: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
