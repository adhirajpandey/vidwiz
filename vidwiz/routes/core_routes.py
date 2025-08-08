from flask import Blueprint, jsonify, render_template, request
from vidwiz.shared.utils import jwt_or_lt_token_required
from vidwiz.shared.models import Video, Note, User, db
from vidwiz.shared.schemas import (
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

core_bp = Blueprint("core", __name__)
logger = get_logger("vidwiz.routes.core_routes")


@core_bp.route("/", methods=["GET"])
def index():
    return render_template("landing.html")


@core_bp.route("/dashboard", methods=["GET"])
def get_dashboard_page():
    return render_template("dashboard.html")


@core_bp.route("/dashboard/<video_id>", methods=["GET"])
def get_video_page(video_id):
    return render_template("video.html")


@core_bp.route("/profile", methods=["GET"])
def get_profile_page():
    return render_template("profile.html")


@core_bp.route("/search", methods=["GET"])
@jwt_or_lt_token_required
def get_search_results():
    query = request.args.get("query", None)
    if query is None:
        logger.warning("Search request missing 'query' parameter")
        return jsonify({"error": "Query parameter is required"}), 400
    # Only include videos that have at least one note owned by the current user
    logger.info(f"Searching videos for user_id={request.user_id}, query='{query}'")
    videos = (
        Video.query.filter(Video.title.ilike(f"%{query}%"))
        .join(Note, Video.video_id == Note.video_id)
        .filter(Note.user_id == request.user_id)
        .group_by(Video.id)
        .order_by(Video.created_at.desc())
        .all()
    )
    if not videos:
        logger.info("Search returned 0 videos")
        return jsonify({"error": "No videos found matching the query"}), 404
    all_videos = [
        {"video_id": video.video_id, "video_title": video.title} for video in videos
    ]
    logger.info(f"Search returned {len(all_videos)} videos")
    return jsonify(all_videos), 200


@core_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            logger.warning("Signup attempt missing username or password")
            if request.is_json:
                return jsonify({"error": "Username and password required."}), 400
            else:
                return render_template(
                    "signup.html", error="Username and password required"
                ), 200

        if User.query.filter_by(username=username).first():
            logger.info(f"Signup attempt with existing username='{username}'")
            if request.is_json:
                return jsonify({"error": "Username already exists."}), 400
            else:
                return render_template(
                    "signup.html", error="Username already exists"
                ), 200

        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        logger.info(f"User created successfully username='{username}', id={user.id}")

        if request.is_json:
            return jsonify({"message": "User created successfully"}), 201
        else:
            from flask import redirect, url_for

            return redirect(url_for("core.login"))

    return render_template("signup.html")


@core_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            logger.warning("Login attempt missing username or password")
            if request.is_json:
                return jsonify({"error": "Username and password required."}), 400
            else:
                return render_template(
                    "login.html", error="Username and password required"
                ), 200

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            logger.warning(f"Invalid login for username='{username}'")
            if request.is_json:
                return jsonify({"error": "Invalid username or password."}), 401
            else:
                return render_template(
                    "login.html", error="Invalid username or password"
                ), 200

        token = jwt.encode(
            {
                "user_id": user.id,
                "username": user.username,
                "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )

        if request.is_json:
            logger.info(f"Login success username='{username}', user_id={user.id}")
            return jsonify({"token": token})
        else:
            from flask import redirect, url_for

            return redirect(url_for("core.get_dashboard_page"))

    return render_template("login.html")


@core_bp.route("/user/token", methods=["POST", "DELETE"])
@jwt_or_lt_token_required
def manage_long_term_token():
    """Manage long-term token - generate with POST or revoke with DELETE"""
    try:
        user = User.query.get(request.user_id)
        if not user:
            logger.warning(f"Long-term token action for missing user_id={request.user_id}")
            return jsonify({"error": "User not found"}), 404

        if request.method == "POST":
            # Check if a long-term token already exists
            if user.long_term_token:
                # Return error - only one token allowed at a time
                logger.warning(f"User_id={user.id} attempted to create duplicate long-term token")
                return jsonify(
                    {
                        "error": "A long-term token already exists. Please revoke the existing token before generating a new one."
                    }
                ), 400

            # Generate a token with no expiry (no 'exp' claim)
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

        elif request.method == "DELETE":
            if not user.long_term_token:
                logger.warning(f"Token revoke requested but none exists for user_id={user.id}")
                return jsonify({"error": "No long-term token found"}), 404

            # Clear the token from the user's record
            user.long_term_token = None
            db.session.commit()
            logger.info(f"Long-term token revoked for user_id={user.id}")

            # Validate response using schema
            response_data = {"message": "Long-term token revoked successfully"}
            validated_response = TokenRevokeResponse(**response_data)
            return jsonify(validated_response.model_dump()), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error in manage_long_term_token: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@core_bp.route("/user/profile", methods=["GET"])
@jwt_or_lt_token_required
def get_profile():
    """Get user profile data"""
    try:
        user = User.query.get(request.user_id)
        if not user:
            logger.warning(f"Profile requested for missing user_id={request.user_id}")
            return jsonify({"error": "User not found"}), 404

        # Extract ai_notes_enabled from profile_data
        ai_notes_enabled = False
        if user.profile_data and isinstance(user.profile_data, dict):
            ai_notes_enabled = user.profile_data.get("ai_notes_enabled", False)

        # Check if token exists
        token_exists = user.long_term_token is not None

        # Construct response data manually
        profile_data = {
            "id": user.id,
            "username": user.username,
            "ai_notes_enabled": ai_notes_enabled,
            "token_exists": token_exists,
        }

        # Validate using schema before sending
        validated_profile = UserProfileRead(**profile_data)
        logger.debug(f"Profile fetched for user_id={user.id}")
        return jsonify(validated_profile.model_dump()), 200

    except Exception as e:
        logger.exception(f"Error in get_profile: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@core_bp.route("/user/profile", methods=["PATCH"])
@jwt_or_lt_token_required
def update_profile():
    """Update user profile data"""
    try:
        data = request.json
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

        # Update the profile_data field with ai_notes_enabled
        if user.profile_data is None:
            user.profile_data = {}

        user.profile_data["ai_notes_enabled"] = update_data.ai_notes_enabled
        flag_modified(user, "profile_data")
        db.session.commit()
        logger.info(f"Updated ai_notes_enabled={update_data.ai_notes_enabled} for user_id={user.id}")

        # Return updated profile data
        token_exists = user.long_term_token is not None
        profile_data = {
            "id": user.id,
            "username": user.username,
            "ai_notes_enabled": update_data.ai_notes_enabled,
            "token_exists": token_exists,
        }

        # Validate using schema before sending
        validated_profile = UserProfileRead(**profile_data)
        return jsonify(validated_profile.model_dump()), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error in update_profile: {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
