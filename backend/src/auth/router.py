from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.auth import service as auth_service
from src.auth.dependencies import get_current_user_id
from src.auth.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    GoogleLoginRequest,
    LoginResponse,
    MessageResponse,
    TokenResponse,
    TokenRevokeResponse,
    UserProfileRead,
    UserProfileUpdate,
)
from src.config import settings
from src.database import get_db
from src.exceptions import (
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    UnauthorizedError,
)


router = APIRouter(prefix="/v2", tags=["Auth"])


@router.post(
    "/auth/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a user account.",
)
def register(
    payload: AuthRegisterRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    if auth_service.find_user_by_email(db, payload.email):
        raise ConflictError("Email already exists")

    auth_service.create_user(db, payload.email, payload.name, payload.password)
    return MessageResponse(message="User created successfully")


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    description="Authenticate and return JWT.",
)
def login(
    payload: AuthLoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise UnauthorizedError("Invalid email or password")

    if not settings.secret_key:
        raise InternalServerError("SECRET_KEY is not configured")

    token = auth_service.generate_jwt_token(
        user,
        settings.secret_key,
        settings.jwt_expiry_hours,
    )
    return LoginResponse(token=token)


@router.post(
    "/auth/google",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    description="Google ID token login.",
)
def google_login(
    payload: GoogleLoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    if not settings.google_client_id:
        raise InternalServerError("Google OAuth not configured")

    try:
        idinfo = auth_service.verify_google_token(
            payload.credential,
            settings.google_client_id,
        )

        google_id = idinfo["sub"]
        email = idinfo.get("email")
        if not email:
            raise BadRequestError("Email is required for Google Sign-In")

        name = idinfo.get("name", email.split("@", 1)[0])
        picture = idinfo.get("picture")

        user = auth_service.upsert_google_user(db, google_id, email, name, picture)

        if not settings.secret_key:
            raise InternalServerError("SECRET_KEY is not configured")

        token = auth_service.generate_jwt_token(
            user,
            settings.secret_key,
            settings.jwt_expiry_hours,
        )
        return LoginResponse(token=token)
    except ValueError:
        raise UnauthorizedError("Invalid Google credential")


@router.post(
    "/auth/tokens",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    description="Create long-term token.",
)
def create_long_term_token(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TokenResponse:
    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")

    if user.long_term_token:
        raise BadRequestError(
            "A long-term token already exists. Please revoke the existing token before generating a new one."
        )

    if not settings.secret_key:
        raise InternalServerError("SECRET_KEY is not configured")

    long_term_token = auth_service.create_long_term_token(db, user, settings.secret_key)
    return TokenResponse(
        message="Long-term token generated successfully",
        token=long_term_token,
    )


@router.delete(
    "/auth/tokens",
    response_model=TokenRevokeResponse,
    status_code=status.HTTP_200_OK,
    description="Revoke long-term token.",
)
def revoke_long_term_token(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> TokenRevokeResponse:
    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")

    if not user.long_term_token:
        raise NotFoundError("No long-term token found")

    auth_service.revoke_long_term_token(db, user)
    return TokenRevokeResponse(message="Long-term token revoked successfully")


@router.get(
    "/users/me",
    response_model=UserProfileRead,
    status_code=status.HTTP_200_OK,
    description="Fetch current profile.",
    tags=["Users"],
)
def get_profile(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> UserProfileRead:
    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")

    profile_data = auth_service.build_profile_data(user, include_long_term_token=True)
    return UserProfileRead.model_validate(profile_data)


@router.patch(
    "/users/me",
    response_model=UserProfileRead,
    status_code=status.HTTP_200_OK,
    description="Update profile fields.",
    tags=["Users"],
)
def update_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> UserProfileRead:
    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")

    updated = auth_service.update_profile(
        db,
        user,
        payload.name,
        payload.ai_notes_enabled,
    )
    profile_data = auth_service.build_profile_data(
        updated, include_long_term_token=False
    )
    return UserProfileRead.model_validate(profile_data)
