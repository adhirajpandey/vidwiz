from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from src.models import ApiModel


class ViewerContext(ApiModel):
    user_id: int | None = None
    guest_session_id: str | None = None


class AuthRegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=7)
    name: str = Field(min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty")
        return trimmed


class AuthLoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class GoogleLoginRequest(ApiModel):
    credential: str = Field(min_length=1)


class MessageResponse(ApiModel):
    message: str


class LoginResponse(ApiModel):
    token: str


class TokenResponse(ApiModel):
    message: str
    token: str


class TokenRevokeResponse(ApiModel):
    message: str


class UserProfileRead(ApiModel):
    id: int
    email: str
    name: str | None = None
    profile_image_url: str | None = None
    ai_notes_enabled: bool
    token_exists: bool
    credits_balance: int
    long_term_token: str | None = None
    created_at: datetime | None = None


class UserProfileUpdate(ApiModel):
    ai_notes_enabled: bool | None = None
    name: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Name must be at least 2 characters long")
        if len(trimmed) > 100:
            raise ValueError("Name must be less than 100 characters")
        return trimmed
