from datetime import datetime, timedelta, timezone
import hashlib
import secrets

import jwt
import logging
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.security import check_password_hash, generate_password_hash

from src.auth.models import ApiToken, User
from src.credits import service as credits_service

logger = logging.getLogger(__name__)


def find_user_by_email(db: Session, email: str) -> User | None:
    logger.debug("Finding user by email", extra={"email": email})
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, email: str, name: str, password: str) -> User:
    logger.debug("Creating user", extra={"email": email})
    user = User(
        email=email,
        name=name,
        password_hash=generate_password_hash(password),
        profile_data={"ai_moments_default": True},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    credits_service.grant_signup_credits(db, user)
    logger.debug("Created user", extra={"user_id": user.id})
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    logger.debug("Authenticating user", extra={"email": email})
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash:
        logger.debug(
            "Authentication failed (missing user/password)", extra={"email": email}
        )
        return None
    if not check_password_hash(user.password_hash, password):
        logger.debug("Authentication failed (invalid password)", extra={"email": email})
        return None
    logger.debug("Authentication successful", extra={"user_id": user.id})
    return user


def generate_jwt_token(user: User, secret_key: str, expiry_hours: int) -> str:
    logger.debug(
        "Generating JWT token", extra={"user_id": user.id, "expiry_hours": expiry_hours}
    )
    return jwt.encode(
        {
            "user_id": user.id,
            "email": user.email,
            "name": user.name or user.email,
            "profile_image_url": user.profile_image_url,
            "exp": datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
        },
        secret_key,
        algorithm="HS256",
    )


def get_user_by_id(db: Session, user_id: int) -> User | None:
    logger.debug("Fetching user by id", extra={"user_id": user_id})
    return db.query(User).filter(User.id == user_id).first()


API_TOKEN_PREFIX = "vw_"


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_api_token(db: Session, user_id: int, name: str) -> tuple[ApiToken, str]:
    logger.debug("Creating API token", extra={"user_id": user_id})
    token = API_TOKEN_PREFIX + secrets.token_urlsafe(32)
    api_token = ApiToken(
        user_id=user_id,
        name=name,
        token_hash=hash_api_token(token),
        token_hint=token[-4:],
    )
    db.add(api_token)
    db.commit()
    db.refresh(api_token)
    return api_token, token


def list_api_tokens(db: Session, user_id: int) -> list[ApiToken]:
    return (
        db.execute(
            select(ApiToken)
            .where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
            .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
        )
        .scalars()
        .all()
    )


def revoke_api_token(db: Session, user_id: int, token_id: int) -> bool:
    api_token = db.execute(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.user_id == user_id,
            ApiToken.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if api_token is None:
        return False
    logger.debug("Revoking API token", extra={"user_id": user_id, "token_id": token_id})
    api_token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def authenticate_api_token(db: Session, token: str) -> int | None:
    """Return the owner of an active token and record its use."""
    api_token = db.execute(
        select(ApiToken).where(
            ApiToken.token_hash == hash_api_token(token),
            ApiToken.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if api_token is None:
        return None
    api_token.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return api_token.user_id


def ai_moments_default(user: User) -> bool:
    if user.profile_data and isinstance(user.profile_data, dict):
        return bool(user.profile_data.get("ai_moments_default", False))
    return False


def build_profile_data(user: User) -> dict:
    logger.debug("Building profile data", extra={"user_id": user.id})
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_image_url": user.profile_image_url,
        "ai_moments_default": ai_moments_default(user),
        "credits_balance": user.credits_balance,
        "created_at": user.created_at,
    }


def update_profile(
    db: Session,
    user: User,
    name: str | None,
    ai_moments_default: bool | None,
) -> User:
    logger.debug(
        "Updating profile",
        extra={
            "user_id": user.id,
            "name_provided": name is not None,
            "ai_moments_default_provided": ai_moments_default is not None,
        },
    )
    if name is not None:
        user.name = name
    if ai_moments_default is not None:
        if user.profile_data is None:
            user.profile_data = {}
        user.profile_data["ai_moments_default"] = ai_moments_default
        flag_modified(user, "profile_data")

    db.commit()
    db.refresh(user)
    logger.debug("Updated profile", extra={"user_id": user.id})
    return user


def verify_google_token(credential: str, google_client_id: str):
    logger.debug("Verifying Google token")
    return id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        google_client_id,
    )


def upsert_google_user(
    db: Session,
    google_id: str,
    email: str,
    name: str,
    picture: str | None,
) -> User:
    logger.debug(
        "Upserting Google user", extra={"google_id": google_id, "email": email}
    )
    user = db.query(User).filter(User.google_id == google_id).first()
    created = False

    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id

    if not user:
        user = User(
            email=email,
            google_id=google_id,
            name=name,
            profile_image_url=picture,
            profile_data={"ai_moments_default": True},
        )
        db.add(user)
        created = True

    if user and not user.name:
        user.name = name

    if user and picture:
        user.profile_image_url = picture

    db.commit()
    db.refresh(user)
    if created:
        credits_service.grant_signup_credits(db, user)
    logger.debug("Upserted Google user", extra={"user_id": user.id, "created": created})
    return user
