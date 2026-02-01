from flask import Blueprint, jsonify, request
from vidwiz.shared.utils import jwt_or_lt_token_required, require_json_body
from vidwiz.shared.schemas import (
    UserCreate,
    UserLogin,
    UserProfileRead,
    UserProfileUpdate,
    TokenResponse,
    TokenRevokeResponse,
    MessageResponse,
    LoginResponse,
    GoogleLoginRequest,
)
from vidwiz.shared.errors import (
    handle_validation_error,
    NotFoundError,
    BadRequestError,
    UnauthorizedError,
    ConflictError,
    InternalServerError,
)
from flask import current_app
from pydantic import ValidationError
from vidwiz.shared.logging import get_logger
from vidwiz.services.user_service import (
    find_user_by_email,
    create_user,
    authenticate_user,
    generate_jwt_token,
    get_user_by_id,
    create_long_term_token as create_long_term_token_record,
    revoke_long_term_token as revoke_long_term_token_record,
    build_profile_data,
    update_profile as update_profile_record,
    verify_google_token,
    upsert_google_user,
)

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

    if find_user_by_email(user_data.email):
        logger.info(f"Signup attempt with existing email='{user_data.email}'")
        raise ConflictError("Email already exists")

    user = create_user(user_data.email, user_data.name, user_data.password)
    logger.info(
        f"User created successfully email='{user_data.email}', id={user.id}"
    )

    return jsonify(MessageResponse(message="User created successfully").model_dump()), 201


@user_bp.route("/user/login", methods=["POST"])
@require_json_body
def login():
    try:
        login_data = UserLogin.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Login validation error: {e}")
        return handle_validation_error(e)

    user = authenticate_user(login_data.email, login_data.password)
    if not user:
        logger.warning(f"Invalid login for email='{login_data.email}'")
        raise UnauthorizedError("Invalid email or password")

    token = generate_jwt_token(
        user,
        current_app.config["SECRET_KEY"],
        current_app.config["JWT_EXPIRY_HOURS"],
    )

    logger.info(f"Login success email='{login_data.email}', user_id={user.id}")
    return jsonify(LoginResponse(token=token).model_dump()), 200


@user_bp.route("/user/token", methods=["POST"])
@jwt_or_lt_token_required
def create_long_term_token():
    """Generate a new long-term token"""
    user = get_user_by_id(request.user_id)
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

    long_term_token = create_long_term_token_record(
        user,
        current_app.config["SECRET_KEY"],
    )
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
    user = get_user_by_id(request.user_id)
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

    revoke_long_term_token_record(user)
    logger.info(f"Long-term token revoked for user_id={user.id}")

    response_data = {"message": "Long-term token revoked successfully"}
    validated_response = TokenRevokeResponse.model_validate(response_data)
    return jsonify(validated_response.model_dump()), 200


@user_bp.route("/user/profile", methods=["GET"])
@jwt_or_lt_token_required
def get_profile():
    """Get user profile data"""
    user = get_user_by_id(request.user_id)
    if not user:
        logger.warning(f"Profile requested for missing user_id={request.user_id}")
        raise NotFoundError("User not found")

    profile_data = build_profile_data(user, include_long_term_token=True)
    validated_profile = UserProfileRead.model_validate(profile_data)
    logger.info(f"Profile fetched for user_id={user.id}")
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

    user = get_user_by_id(request.user_id)
    if not user:
        logger.warning(f"Update profile for missing user_id={request.user_id}")
        raise NotFoundError("User not found")

    user = update_profile_record(
        user,
        update_data.name,
        update_data.ai_notes_enabled,
    )
    logger.info(f"Updated profile for user_id={user.id}")

    profile_data = build_profile_data(user, include_long_term_token=False)
    validated_profile = UserProfileRead.model_validate(profile_data)
    return jsonify(validated_profile.model_dump()), 200


@user_bp.route("/user/google/login", methods=["POST"])
@require_json_body
def google_login():
    """
    Handle Google Sign-In from the frontend.
    Frontend sends Google ID token (credential), backend verifies it and creates/logs in user.
    """
    try:
        google_data = GoogleLoginRequest.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Google login validation error: {e}")
        return handle_validation_error(e)

    credential = google_data.credential

    google_client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not google_client_id:
        logger.error("GOOGLE_CLIENT_ID not configured")
        raise InternalServerError("Google OAuth not configured")

    try:
        # Verify the Google ID token
        idinfo = verify_google_token(credential, google_client_id)

        # Extract user info from the verified token
        google_id = idinfo["sub"]
        email = idinfo.get("email")
        
        if not email:
            logger.warning("Google login without email - email is required")
            raise BadRequestError("Email is required for Google Sign-In")
        
        name = idinfo.get("name", email.split("@")[0])
        picture = idinfo.get("picture")  # Profile image URL from Google

        logger.info(f"Google login attempt for google_id={google_id}, email={email}")

        user = upsert_google_user(google_id, email, name, picture)

        # Generate JWT token
        token = generate_jwt_token(
            user,
            current_app.config["SECRET_KEY"],
            current_app.config["JWT_EXPIRY_HOURS"],
        )

        logger.info(f"Google login success for user_id={user.id}, email='{user.email}'")
        return jsonify(LoginResponse(token=token).model_dump()), 200

    except ValueError as e:
        # Invalid token
        logger.warning(f"Invalid Google token: {e}")
        raise UnauthorizedError("Invalid Google credential")
