from datetime import datetime, timedelta, timezone

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.security import check_password_hash, generate_password_hash

from src.auth.models import User
from src.credits import service as credits_service


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, email: str, name: str, password: str) -> User:
    user = User(
        email=email,
        name=name,
        password_hash=generate_password_hash(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    credits_service.grant_signup_credits(db, user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash:
        return None
    if not check_password_hash(user.password_hash, password):
        return None
    return user


def generate_jwt_token(user: User, secret_key: str, expiry_hours: int) -> str:
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
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_long_term_token(db: Session, token: str) -> User | None:
    return db.query(User).filter(User.long_term_token == token).first()


def create_long_term_token(db: Session, user: User, secret_key: str) -> str:
    long_term_token = jwt.encode(
        {
            "user_id": user.id,
            "email": user.email,
            "type": "long_term",
            "iat": datetime.now(timezone.utc).timestamp(),
        },
        secret_key,
        algorithm="HS256",
    )
    user.long_term_token = long_term_token
    db.commit()
    db.refresh(user)
    return long_term_token


def revoke_long_term_token(db: Session, user: User) -> None:
    user.long_term_token = None
    db.commit()


def build_profile_data(user: User, include_long_term_token: bool = True) -> dict:
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
        "credits_balance": user.credits_balance,
        "created_at": user.created_at,
    }

    if include_long_term_token:
        profile_data["long_term_token"] = user.long_term_token

    return profile_data


def update_profile(
    db: Session,
    user: User,
    name: str | None,
    ai_notes_enabled: bool | None,
) -> User:
    if name is not None:
        user.name = name
    if ai_notes_enabled is not None:
        if user.profile_data is None:
            user.profile_data = {}
        user.profile_data["ai_notes_enabled"] = ai_notes_enabled
        flag_modified(user, "profile_data")

    db.commit()
    db.refresh(user)
    return user


def verify_google_token(credential: str, google_client_id: str):
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
    return user
