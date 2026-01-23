from pydantic import BaseModel, field_validator, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoCreate(BaseModel):
    video_id: str
    title: str
    transcript_available: Optional[bool] = False


class VideoRead(BaseModel):
    id: int
    video_id: str
    title: Optional[str]
    metadata: Optional[dict] = Field(default=None, validation_alias="video_metadata")
    transcript_available: bool
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    transcript_available: Optional[bool] = None

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class VideoPatch(BaseModel):
    """Schema for admin PATCH /videos/<video_id> endpoint (e.g., Lambda updating summary)."""

    summary: Optional[str] = None

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v):
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("summary must be a string")
            if len(v) > 10000:
                raise ValueError("summary must be less than 10000 characters")
        return v

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class NoteCreate(BaseModel):
    video_id: str
    video_title: Optional[str] = None
    timestamp: str
    text: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_contain_colon(cls, v):
        if ":" not in v:
            raise ValueError("timestamp must contain at least one ':'")
        if sum(c.isdigit() for c in v) < 2:
            raise ValueError("timestamp must contain at least two numbers")
        return v


class NoteRead(BaseModel):
    id: int
    video_id: str
    timestamp: str
    text: Optional[str]
    generated_by_ai: bool
    created_at: datetime
    updated_at: datetime
    video: Optional[VideoRead] = None
    user_id: int
    model_config = {"from_attributes": True}


class NoteUpdate(BaseModel):
    text: str
    generated_by_ai: Optional[bool] = None

    @field_validator("text")
    @classmethod
    def validate_string_type(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("Field must be a string")
        return v

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class TranscriptResult(BaseModel):
    task_id: int
    video_id: str
    success: bool
    transcript: Optional[list] = None
    error_message: Optional[str] = None

    @field_validator("transcript")
    @classmethod
    def validate_transcript_format(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("transcript must be a list")
            for item in v:
                if not isinstance(item, dict):
                    raise ValueError("transcript items must be dictionaries")
                if "text" not in item:
                    raise ValueError("transcript items must contain 'text' field")
        return v


class MetadataResult(BaseModel):
    task_id: int
    video_id: str
    success: bool
    metadata: Optional[dict] = None
    error_message: Optional[str] = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata_format(cls, v):
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("metadata must be a dictionary")
        return v


class UserCreate(BaseModel):
    email: str
    password: str
    name: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        v = v.strip().lower()
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not v:
            raise ValueError("Password cannot be empty")
        if len(v) <= 6:
            raise ValueError("Password must be more than 6 characters long")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters long")
        if len(v) > 100:
            raise ValueError("Name must be less than 100 characters")
        return v

    model_config = {
        "extra": "forbid",
    }


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not v:
            raise ValueError("Password cannot be empty")
        return v

    model_config = {
        "extra": "forbid",
    }


class UserProfileRead(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    profile_image_url: Optional[str] = None
    ai_notes_enabled: bool
    token_exists: bool
    long_term_token: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    ai_notes_enabled: Optional[bool] = None
    name: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Name must be at least 2 characters long")
            if len(v) > 100:
                raise ValueError("Name must be less than 100 characters")
        return v

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class TokenResponse(BaseModel):
    message: str
    token: str
    model_config = {"from_attributes": True}


class TokenRevokeResponse(BaseModel):
    message: str
    model_config = {"from_attributes": True}


class WizInitRequest(BaseModel):
    video_id: str

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, v):
        if not v or not v.strip():
            raise ValueError("video_id cannot be empty")
        return v.strip()

    model_config = {
        "extra": "forbid",
    }


class WizVideoStatusResponse(BaseModel):
    video_id: str
    title: Optional[str] = None
    transcript_available: bool
    metadata: Optional[dict] = None
    summary: Optional[str] = None
    model_config = {"from_attributes": True}
